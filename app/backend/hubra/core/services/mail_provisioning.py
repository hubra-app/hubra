"""MailProvisioningService — idempotent WildDuck provisioning primitives.

Every category (system, group, function, member) calls these same primitives.
All methods are safe to call repeatedly (idempotent). They write
``sync_state`` / ``last_synced_at`` on the row and raise ``WildDuckError``
only on unexpected failures (network error, auth failure, etc.); a 404 is
tolerated as "already absent".
"""

from __future__ import annotations

import json
import logging
import re
import secrets
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from hubra.core.extensions import db
from hubra.core.models.managed_mail import ManagedMailAddress
from hubra.core.services.wildduck import (
    WildDuckError,
    make_username,
    try_get_client,
)

_log = logging.getLogger(__name__)

# ── Category defaults (overridable per-mailbox) ──────────────────────────

CATEGORY_DEFAULTS: dict[str, dict[str, Any]] = {
    "system": {"quota_bytes": 200 * 1024 * 1024, "retention": 30 * 86400 * 1000},
    "group": {"quota_bytes": 200 * 1024 * 1024, "retention": 30 * 86400 * 1000},
    "function": {"quota_bytes": 200 * 1024 * 1024, "retention": 30 * 86400 * 1000},
    "member": {"quota_bytes": 1024 * 1024 * 1024, "retention": None},
}


def _category_default(kind: str, field: str) -> Any:
    return CATEGORY_DEFAULTS.get(kind, {}).get(field)


def _effective_quota(mma: ManagedMailAddress) -> int:
    """Return effective quota in bytes for *mma*.

    Priority: mailbox-specific > system setting > category default > 200 MB.
    """
    if mma.quota_bytes is not None:
        return mma.quota_bytes
    # Check system-level default quota setting (admin-configurable).
    try:
        from hubra.api.settings.services import SettingService

        raw = SettingService.get("mail.quota_default_bytes")
        if raw is not None:
            return int(raw)
    except (ValueError, TypeError):
        pass
    default = _category_default(mma.kind or "", "quota_bytes")
    return default if default is not None else 200 * 1024 * 1024


def _effective_retention(mma: ManagedMailAddress) -> int | None:
    if mma.retention is not None:
        if mma.retention <= 0:
            return None
        return mma.retention
    default = _category_default(mma.kind or "", "retention")
    if default is None:
        return None
    return default


# ── Collision resolver ──────────────────────────────────────────────────


def resolve_local_part(
    desired: str, kind: str | None = None, owner_id: int | None = None
) -> str:
    """Resolve a unique local part for the given *desired* name.

    Normalisation:
      1. lowercase
      2. replace umlauts: ä→ae, ö→oe, ü→ue, ß→ss
      3. replace runs of non-alphanumeric with a single dot
      4. strip leading/trailing dots and hyphens
      5. truncate to 64 chars

    If the normalised form is taken (via UNIQUE(local_part, domain)), append
    the smallest integer suffix that is free (``name2``, ``name3``, …).

    Reservation happens in the caller's transaction.
    """
    normalized = _normalize_local_part(desired)
    if not normalized:
        normalized = "mail"

    domain = _get_club_domain()
    if not domain:
        return normalized

    # Check if free
    existing = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.local_part == normalized,
            ManagedMailAddress.domain == domain,
        )
    )
    if existing is None:
        return normalized

    # Suffix loop
    suffix = 2
    while True:
        candidate = f"{normalized}{suffix}"
        existing = db.session.scalar(
            select(ManagedMailAddress).where(
                ManagedMailAddress.local_part == candidate,
                ManagedMailAddress.domain == domain,
            )
        )
        if existing is None:
            return candidate
        suffix += 1


def _normalize_local_part(s: str) -> str:
    s = s.lower().strip()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    s = re.sub(r"[^a-z0-9.-]", ".", s)
    s = re.sub(r"\.{2,}", ".", s)
    s = s.strip(".-")
    return s[:64]


def _get_club_domain() -> str:
    from hubra.api.settings.services import SettingService

    return SettingService.get("mail.domain", default="") or ""


def _get_hub_address() -> str:
    from hubra.api.settings.services import SettingService

    hub_prefix = (
        SettingService.get("Club.Mail.SystemHubPrefix", default="postmaster")
        or "postmaster"
    )
    return f"{hub_prefix}@{_get_club_domain()}"


def _resolve_system_alias_targets(mma: ManagedMailAddress) -> list[str]:
    """Resolve forward targets for a system alias MMA.

    Handles the ``"hub"`` marker — replaces it with the configured hub address.
    If no fixed targets are set, falls back to the hub address.
    """
    raw: list[str] = []
    if mma.fixed_forward_targets:
        try:
            raw = json.loads(mma.fixed_forward_targets)
        except (json.JSONDecodeError, TypeError):
            raw = []

    hub = _get_hub_address()
    resolved: list[str] = []
    for t in raw:
        if t == "hub":
            resolved.append(hub)
        else:
            resolved.append(t)

    if not resolved:
        resolved = [hub]

    return resolved


def _resolve_system_forward_targets(mma: ManagedMailAddress) -> list[str]:
    """Resolve forwarding targets for a system mailbox MMA.

    If ``fixed_forward_targets`` is set, parse and resolve ``"hub"`` markers.
    If not set but ``owner_type`` is ``"group"``, resolve from group members.
    If not set and no group, return empty list (no forwarding).
    """
    if mma.fixed_forward_targets:
        try:
            raw = json.loads(mma.fixed_forward_targets)
        except (json.JSONDecodeError, TypeError):
            raw = []
        hub = _get_hub_address()
        return [hub if t == "hub" else t for t in raw]

    if mma.owner_type == "group" and mma.owner_id is not None:
        targets = _resolve_group_member_targets(mma.owner_id)
        if targets:
            return targets

    return []


def _resolve_group_member_targets(group_id: int) -> list[str]:
    """Resolve forward targets for a group mailbox from current members.

    Queries ``Member.public_email`` joined through ``member_groups`` where
    the member is not archived and has a public email. Falls back to the
    hub address if no targets are found.
    """
    from hubra.core.models.member import Member, member_groups

    targets = list(
        db.session.scalars(
            select(Member.public_email)
            .join(member_groups, Member.id == member_groups.c.member_id)
            .where(member_groups.c.group_id == group_id)
            .where(Member.archived_at.is_(None))
            .where(Member.public_email.isnot(None))
        ).all()
    )
    targets = [t for t in targets if t]

    if not targets:
        hub = _get_hub_address()
        if hub:
            targets = [hub]

    return targets  # type: ignore[return-value]


def _resolve_group_alias_targets(mma: ManagedMailAddress) -> list[str]:
    """Resolve forward targets for an additional group alias MMA.

    Additional group aliases forward to the primary group alias address
    (not directly to members), so all fan-out logic lives in one place.
    Falls back to resolving member emails directly, then the hub address.
    """
    primary = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "group",
            ManagedMailAddress.owner_id == mma.owner_id,
            ManagedMailAddress.fixed_forward_targets.is_(None),
            ManagedMailAddress.id != mma.id,
        )
    )
    if primary is not None:
        return [primary.address]

    if mma.owner_id is not None:
        targets = _resolve_group_member_targets(mma.owner_id)
        if targets:
            return targets

    hub = _get_hub_address()
    return [hub] if hub else []


def _resolve_function_holder_targets(function_id: int) -> list[str]:
    """Resolve forward targets for a function mailbox from current holders.

    Queries ``Member.public_email`` joined through ``function_holders``
    where the member is not archived and has a public email.
    Falls back to the hub address if no targets are found.
    """
    from hubra.core.models.function import FunctionHolder
    from hubra.core.models.member import Member

    targets = list(
        db.session.scalars(
            select(Member.public_email)
            .join(FunctionHolder, FunctionHolder.member_id == Member.id)
            .where(FunctionHolder.function_id == function_id)
            .where(Member.archived_at.is_(None))
            .where(Member.public_email.isnot(None))
        ).all()
    )
    targets = [t for t in targets if t]

    if not targets:
        hub = _get_hub_address()
        if hub:
            targets = [hub]

    return targets  # type: ignore[return-value]


def _resolve_function_alias_targets(mma: ManagedMailAddress) -> list[str]:
    """Resolve forward targets for an additional function alias MMA.

    Additional function aliases forward to the primary function alias
    address (not directly to holders), so all fan-out logic lives in
    one place. Falls back to resolving holder emails directly, then the
    hub address.
    """
    primary = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "function",
            ManagedMailAddress.owner_id == mma.owner_id,
            ManagedMailAddress.fixed_forward_targets.is_(None),
            ManagedMailAddress.id != mma.id,
        )
    )
    if primary is not None:
        return [primary.address]

    if mma.owner_id is not None:
        targets = _resolve_function_holder_targets(mma.owner_id)
        if targets:
            return targets

    hub = _get_hub_address()
    return [hub] if hub else []


def _resolve_member_forward_targets(mma: ManagedMailAddress) -> list[str]:
    """Resolve forward targets for a member mailbox MMA.

    When forwarding is enabled, returns ``[member.email]`` (the member's
    private email) so WildDuck stores a copy in the mailbox AND forwards.
    Includes loop detection: if the private email domain matches the club
    domain, returns empty to prevent a mail loop.
    """
    fwd_enabled = mma.forward_enabled
    if fwd_enabled is None:
        fwd_enabled = mma.forwarding_enabled
    if not fwd_enabled:
        return []

    from hubra.core.models.member import Member

    member = db.session.get(Member, mma.owner_id)
    if member is None or not member.email:
        return []

    private_domain = member.email.split("@")[-1].lower() if "@" in member.email else ""
    club_domain = _get_club_domain()
    if club_domain and private_domain == club_domain:
        return []

    return [member.email]


# ── Mark helpers ────────────────────────────────────────────────────────


def _mark_ok(mma: ManagedMailAddress) -> None:
    mma.sync_state = "ok"
    mma.last_synced_at = datetime.now(timezone.utc)
    mma.sync_error = None


def _mark_error(mma: ManagedMailAddress, error: str) -> None:
    mma.sync_state = "error"
    mma.sync_error = error[:500]


# ── Provisioning primitives ─────────────────────────────────────────────


def _migrate_legacy_id(mma: ManagedMailAddress) -> None:
    """Copy legacy ``wildduck_user_id`` to the unified ``wildduck_id`` column."""
    if not mma.wildduck_id and getattr(mma, "wildduck_user_id", None):
        mma.wildduck_id = mma.wildduck_user_id


def ensure_mailbox(
    mma: ManagedMailAddress, *, password_hash: str | None = None
) -> None:
    """Create-or-update a WildDuck user (mailbox) for *mma*.

    If the user already exists (``mma.wildduck_id`` is set and resolves),
    it is updated to reflect current quota/retention/targets. Otherwise a
    new user is created.

    When *password_hash* is provided, it is set on the user with the
    ``hashedPassword`` flag (for member mailboxes). System mailboxes
    use a placeholder.
    """
    _migrate_legacy_id(mma)

    wd = try_get_client()
    if wd is None:
        _log.debug("ensure_mailbox: WildDuck not configured, skipping %s", mma.address)
        return

    quota_bytes = _effective_quota(mma)
    retention_ms = _effective_retention(mma)
    username = (
        mma.mail_prefix
        or mma.local_part
        or make_username(mma.display_name or "mailbox")
    )

    try:
        if mma.wildduck_id:
            existing = wd.safe_get_user(mma.wildduck_id)
            if existing is None:
                _log.info(
                    "ensure_mailbox: WildDuck user %s not found for MMA %d — re-creating",
                    mma.wildduck_id,
                    mma.id,
                )
                mma.wildduck_id = None

        if mma.wildduck_id is None:
            # No member password to mirror: use an unguessable random one so
            # the mailbox cannot be logged into until a password is set.
            pwd = password_hash or secrets.token_urlsafe(32)
            hashed = bool(password_hash)
            result = wd.create_user(
                username=username,
                name=mma.display_name or username,
                password=pwd,
                quota_mb=quota_bytes // (1024 * 1024) or 1,
                hashed=hashed,
                retention_ms=retention_ms,
            )
            mma.wildduck_id = result.get("id")
            _log.info(
                "ensure_mailbox: created user %s → wd_id=%s",
                mma.address,
                mma.wildduck_id,
            )
        else:
            update: dict[str, Any] = {
                "name": mma.display_name or username,
                "quota": quota_bytes,
            }
            if retention_ms is not None:
                update["retention"] = retention_ms
            wd.update_user_attributes(mma.wildduck_id, **update)
            if password_hash:
                wd.update_user_password(mma.wildduck_id, password_hash, hashed=True)
            _log.debug("ensure_mailbox: updated user %s", mma.address)

        _mark_ok(mma)

        sync_from_whitelist_for_mma(mma)
    except WildDuckError as exc:
        _mark_error(mma, str(exc))
        _log.warning("ensure_mailbox: error for %s: %s", mma.address, exc)
        raise


def ensure_alias(mma: ManagedMailAddress) -> None:
    """Create-or-update a WildDuck address for *mma*.

    For mailbox-backed addresses: ensures the address exists on the WildDuck
    user (``/users/{id}/addresses``).

    For pure aliases: ensures a forwarding alias exists with resolved targets
    (``/addresses/forwarded``). System aliases resolve ``"hub"`` markers.
    """
    _migrate_legacy_id(mma)

    wd = try_get_client()
    if wd is None:
        _log.debug("ensure_alias: WildDuck not configured, skipping %s", mma.address)
        return

    try:
        if mma.address_type == "mailbox":
            if not mma.wildduck_id:
                _log.warning(
                    "ensure_alias: no wildduck_id for mailbox-backed %s", mma.address
                )
                _mark_error(mma, "no wildduck_id")
                return
            _ensure_address_on_user(wd, mma.wildduck_id, mma.address)
        else:
            targets: list[str] = []
            if mma.kind == "system":
                targets = _resolve_system_alias_targets(mma)
            elif mma.kind == "group":
                targets = _resolve_group_alias_targets(mma)
            elif mma.kind == "function":
                targets = _resolve_function_alias_targets(mma)
            elif mma.kind == "alias":
                if mma.fixed_forward_targets:
                    try:
                        targets = json.loads(mma.fixed_forward_targets)
                    except (json.JSONDecodeError, TypeError):
                        targets = []
                if not targets:
                    parent = db.session.get(ManagedMailAddress, mma.owner_id)
                    if parent:
                        targets = [parent.address]
            _ensure_forwarding_alias(wd, mma, targets)
        _mark_ok(mma)
    except WildDuckError as exc:
        _mark_error(mma, str(exc))
        _log.warning("ensure_alias: error for %s: %s", mma.address, exc)
        raise


def _ensure_address_on_user(wd, user_id: str, address: str) -> None:
    """Ensure an address exists on a WildDuck user (no-op if present)."""
    addrs = wd.list_user_addresses(user_id)
    existing = addrs.get("results", [])
    for addr in existing:
        if addr.get("address") == address:
            return
    allow_wildcard = address.startswith("*@")
    wd.add_address_to_user(user_id, address, allow_wildcard=allow_wildcard)


def _ensure_forwarding_alias(
    wd, mma: ManagedMailAddress, targets: list[str] | None = None
) -> None:
    """Ensure a WildDuck forwarding alias exists for *mma*.

    If *targets* is provided, the alias is created with those targets and
    updated if the existing alias has different targets.
    """
    if targets is None:
        targets = []
    targets = [t for t in targets if t and t.lower() != mma.address.lower()]
    if mma.wildduck_id:
        existing = wd.safe_get_address(mma.wildduck_id)
        if existing is not None:
            current_targets = existing.get("targets", [])
            if set(current_targets) != set(targets):
                wd.update_forwarding_alias(mma.wildduck_id, targets)
                _log.info(
                    "ensure_forwarding_alias: updated targets for %s → %s",
                    mma.address,
                    targets,
                )
            return
    result = wd.create_forwarding_alias(
        mma.address, targets=targets, name=mma.display_name or mma.address
    )
    mma.wildduck_id = result.get("id")


def ensure_forwarding(mma: ManagedMailAddress, targets: list[str]) -> None:
    """Reconcile forwarding targets for *mma* to exactly *targets*.

    For mailbox-backed MMAs: updates the WildDuck user's ``targets`` array
    (mailbox retains a copy of every message).

    For alias MMAs: updates the WildDuck forwarding alias's targets.

    If *targets* is empty, forwarding is cleared.
    """
    _migrate_legacy_id(mma)

    wd = try_get_client()
    if wd is None:
        _log.debug(
            "ensure_forwarding: WildDuck not configured, skipping %s", mma.address
        )
        return

    if not mma.wildduck_id:
        _log.warning("ensure_forwarding: no wildduck_id for %s", mma.address)
        _mark_error(mma, "no wildduck_id")
        return

    try:
        if mma.address_type == "mailbox":
            wd.update_user_attributes(mma.wildduck_id, targets=targets)
        else:
            wd.update_forwarding_alias(mma.wildduck_id, targets)
        _log.info(
            "ensure_forwarding: updated targets for %s → %s",
            mma.address,
            targets,
        )
        _mark_ok(mma)
    except WildDuckError as exc:
        _mark_error(mma, str(exc))
        _log.warning("ensure_forwarding: error for %s: %s", mma.address, exc)
        raise


def ensure_absent(mma: ManagedMailAddress) -> None:
    """Remove the WildDuck object for *mma*. Tolerates 404 as success.

    Clears ``wildduck_id`` on the row.
    """
    _migrate_legacy_id(mma)

    wd = try_get_client()
    if wd is None:
        mma.wildduck_id = None
        mma.sync_state = "ok"
        return

    try:
        if mma.address_type == "mailbox" and mma.wildduck_id:
            wd.safe_delete_user(mma.wildduck_id)
        elif mma.wildduck_id:
            wd.safe_delete_address(mma.wildduck_id)
        _log.info("ensure_absent: removed WildDuck object for %s", mma.address)
    except WildDuckError as exc:
        _log.warning("ensure_absent: error for %s: %s", mma.address, exc)
        raise
    finally:
        mma.wildduck_id = None
        mma.sync_state = "ok"


def ensure_catchall(mma: ManagedMailAddress) -> None:
    """Ensure ``*@domain`` is attached to the hub user as a wildcard address.

    The catchall MMA row has ``local_part="*"`` and no ``wildduck_id`` — it
    shares the hub user's WildDuck account. This method:

    1. Resolves the hub address from ``Club.Mail.SystemHubPrefix`` + ``mail.domain``
    2. Finds the hub MMA by local_part + domain
    3. If the hub user is provisioned, ensures ``*@domain`` is attached with
       ``allowWildcard=True``
    4. If the hub is not yet provisioned, logs a warning and marks an error
       (the next reconcile cycle will retry once the hub exists)
    """
    wd = try_get_client()
    if wd is None:
        _log.debug("ensure_catchall: WildDuck not configured, skipping %s", mma.address)
        return

    domain = _get_club_domain()
    if not domain:
        _mark_error(mma, "no mail.domain configured")
        return

    hub_address = _get_hub_address()
    hub_prefix = hub_address.split("@")[0]

    hub_mma = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.local_part == hub_prefix,
            ManagedMailAddress.domain == domain,
        )
    )
    if hub_mma is None or not hub_mma.wildduck_id:
        _log.warning(
            "ensure_catchall: hub %s not provisioned yet — skipping catchall %s",
            hub_address,
            mma.address,
        )
        _mark_error(mma, f"hub {hub_address} not provisioned")
        return

    try:
        catchall_address = f"*@{domain}"
        _ensure_address_on_user(wd, hub_mma.wildduck_id, catchall_address)
        _mark_ok(mma)
        _log.info(
            "ensure_catchall: ensured %s on hub user %s",
            catchall_address,
            hub_address,
        )
    except WildDuckError as exc:
        _mark_error(mma, str(exc))
        _log.warning("ensure_catchall: error for %s: %s", mma.address, exc)
        raise


def set_system_mailbox_password(mma: ManagedMailAddress, password: str) -> None:
    """Push a plaintext password to WildDuck and store it encrypted on the MMA.

    WildDuck hashes the password internally. The plaintext is also stored
    encrypted (Fernet) in ``mailbox_password_encrypted`` so that binding
    sync can write it to an InternalKey. The plaintext is never logged or
    returned by any API response.

    The encrypted password is stored regardless of WildDuck availability —
    so the binding key is populated even before provisioning, and a later
    sync can push it to WildDuck.
    """
    from hubra.core.crypto import encrypt_code

    mma.mailbox_password_encrypted = encrypt_code(
        password, "managed_mail_addresses.mailbox_password_encrypted"
    )

    wd = try_get_client()
    if wd is None:
        _log.debug(
            "set_system_mailbox_password: WildDuck not configured, "
            "password stored encrypted for %s",
            mma.address,
        )
    elif not mma.wildduck_id:
        _log.warning("set_system_mailbox_password: no wildduck_id for %s", mma.address)
        _mark_error(mma, "no wildduck_id")
    else:
        try:
            wd.update_user_password(mma.wildduck_id, password)
            _mark_ok(mma)
            _log.info(
                "set_system_mailbox_password: password updated for %s", mma.address
            )
        except WildDuckError as exc:
            _mark_error(mma, str(exc))
            _log.warning(
                "set_system_mailbox_password: error for %s: %s", mma.address, exc
            )
            raise

    from hubra.core.services.binding_engine import sync_for_source

    sync_for_source("mail_address", str(mma.id))


def migrate_alias_to_mailbox(mma: ManagedMailAddress) -> None:
    """Migrate a group MMA from WildDuck forwarding alias to WildDuck user.

    Deletes the old WildDuck forwarding alias (tracked via
    ``wildduck_id``), clears that ID, then calls ``ensure_mailbox``
    to create a new WildDuck user with a mailbox.
    """
    wd = try_get_client()
    if wd is None:
        _log.debug(
            "migrate_alias_to_mailbox: WildDuck not configured, skipping %s",
            mma.address,
        )
        return

    if mma.wildduck_id and not mma.address_type == "mailbox":
        try:
            wd.safe_delete_address(mma.wildduck_id)
            _log.info(
                "migrate_alias_to_mailbox: deleted old alias %s for %s",
                mma.wildduck_id,
                mma.address,
            )
        except WildDuckError as exc:
            _log.warning(
                "migrate_alias_to_mailbox: failed to delete old alias %s: %s",
                mma.wildduck_id,
                exc,
            )
        finally:
            mma.wildduck_id = None

    ensure_mailbox(mma)


def reconcile_entity_forwarding(entity_type: str, entity_id: int) -> None:
    """Reconcile forwarding targets for a group or function entity.

    For groups: finds the primary mailbox-backed MMA, resolves current
    member ``public_email`` targets, and calls ``ensure_forwarding``.

    For functions: dispatches the old ``sync_managed_address`` Celery task
    for each linked MMA (function mail migration is a separate phase).
    """
    if entity_type == "group":
        mma = db.session.scalar(
            select(ManagedMailAddress).where(
                ManagedMailAddress.owner_type == "group",
                ManagedMailAddress.owner_id == entity_id,
                ManagedMailAddress.fixed_forward_targets.is_(None),
            )
        )
        if mma is None or not mma.enabled:
            return
        if not mma.wildduck_id:
            _log.debug(
                "reconcile_entity_forwarding: group %d MMA not provisioned yet",
                entity_id,
            )
            return
        targets = _resolve_group_member_targets(entity_id)
        ensure_forwarding(mma, targets)

    elif entity_type == "function":
        mma = db.session.scalar(
            select(ManagedMailAddress).where(
                ManagedMailAddress.owner_type == "function",
                ManagedMailAddress.owner_id == entity_id,
                ManagedMailAddress.fixed_forward_targets.is_(None),
            )
        )
        if mma is None or not mma.enabled:
            return
        if not mma.wildduck_id:
            _log.debug(
                "reconcile_entity_forwarding: function %d MMA not provisioned yet",
                entity_id,
            )
            return
        targets = _resolve_function_holder_targets(entity_id)
        ensure_forwarding(mma, targets)


# ── fromWhitelist computation + sync ───────────────────────────────────────


def _parse_from_whitelist_column(mma: ManagedMailAddress) -> list[str]:
    """Parse the admin-curated ``from_whitelist`` JSON column into a list."""
    if not mma.from_whitelist:
        return []
    try:
        parsed = json.loads(mma.from_whitelist)
        if isinstance(parsed, list):
            return [str(x) for x in parsed if isinstance(x, str)]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _get_mma_aliases(mma_id: int) -> list[str]:
    """Return all alias MMA addresses for the given primary MMA."""
    rows = db.session.scalars(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "mail_address",
            ManagedMailAddress.owner_id == mma_id,
        )
    ).all()
    return [r.address for r in rows if r.address]


def _get_member_group_addresses(member_id: int) -> list[str]:
    """Return addresses (primary + aliases) for all groups a member belongs to."""
    from hubra.core.models.member import member_groups

    group_ids = (
        db.session.execute(
            select(member_groups.c.group_id).where(
                member_groups.c.member_id == member_id
            )
        )
        .scalars()
        .all()
    )

    addresses: list[str] = []
    for gid in group_ids:
        mmas = db.session.scalars(
            select(ManagedMailAddress).where(
                ManagedMailAddress.owner_type == "group",
                ManagedMailAddress.owner_id == gid,
            )
        ).all()
        for mma in mmas:
            addresses.append(mma.address)
            addresses.extend(_get_mma_aliases(mma.id))
    return addresses


def _get_member_function_addresses(member_id: int) -> list[str]:
    """Return addresses (primary + aliases) for all functions a member holds."""
    from hubra.core.models.function import FunctionHolder

    fn_ids = (
        db.session.execute(
            select(FunctionHolder.function_id).where(
                FunctionHolder.member_id == member_id
            )
        )
        .scalars()
        .all()
    )

    addresses: list[str] = []
    for fid in fn_ids:
        mmas = db.session.scalars(
            select(ManagedMailAddress).where(
                ManagedMailAddress.owner_type == "function",
                ManagedMailAddress.owner_id == fid,
            )
        ).all()
        for mma in mmas:
            addresses.append(mma.address)
            addresses.extend(_get_mma_aliases(mma.id))
    return addresses


def _is_sender_mma(mma: ManagedMailAddress) -> bool:
    """Return True if this MMA is the outbound auth (sender) mailbox."""
    from hubra.core.services.key_service import KeyService

    sender = KeyService.get("mail.smtp.user")
    if not sender:
        return False
    return mma.address == str(sender)


def compute_effective_from_whitelist(mma: ManagedMailAddress) -> list[str]:
    """Compute the effective fromWhitelist for a mailbox MMA.

    Combines:
    - The mailbox's own address
    - The mailbox's own MailAlias addresses
    - For members: group + function addresses they may send-as
    - For the sender: the ``mail.system.senders`` binding-driven list
    - Admin-curated entries from the ``from_whitelist`` column
    """
    whitelist: list[str] = [mma.address]

    whitelist.extend(_get_mma_aliases(mma.id))

    if mma.kind == "member" and mma.owner_id:
        whitelist.extend(_get_member_group_addresses(mma.owner_id))
        whitelist.extend(_get_member_function_addresses(mma.owner_id))

    if _is_sender_mma(mma):
        from hubra.core.services.key_service import KeyService

        system_senders = KeyService.get("mail.system.senders")
        if isinstance(system_senders, list):
            whitelist.extend(str(s) for s in system_senders if isinstance(s, str))
        elif system_senders:
            whitelist.append(str(system_senders))

    whitelist.extend(_parse_from_whitelist_column(mma))

    deduped: list[str] = []
    for addr in whitelist:
        if addr and addr not in deduped:
            deduped.append(addr)
    return sorted(deduped)


def sync_from_whitelist_for_mma(mma: ManagedMailAddress) -> None:
    """Push the effective fromWhitelist to the WildDuck user for *mma*.

    Safe to call repeatedly — overwrites the WildDuck value with the
    computed list. No-op if WildDuck is not configured or the MMA has
    no WildDuck user.
    """
    if mma.address_type != "mailbox":
        return

    wd = try_get_client()
    if wd is None:
        _log.debug(
            "sync_from_whitelist_for_mma: WildDuck not configured, skipping %s",
            mma.address,
        )
        return

    if not mma.wildduck_id:
        _log.debug(
            "sync_from_whitelist_for_mma: no wildduck_id for %s, skipping",
            mma.address,
        )
        return

    whitelist = compute_effective_from_whitelist(mma)
    try:
        wd.update_user(mma.wildduck_id, fromWhitelist=whitelist)
        _log.info(
            "sync_from_whitelist_for_mma: updated fromWhitelist for %s (%d entries)",
            mma.address,
            len(whitelist),
        )
    except WildDuckError as exc:
        _log.warning("sync_from_whitelist_for_mma: error for %s: %s", mma.address, exc)
