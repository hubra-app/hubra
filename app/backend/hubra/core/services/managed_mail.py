"""Managed mail address provisioning and sync service.

Single entry point for creating, updating, and deprovisioning WildDuck
mail resources (users, aliases, filters) for all club-managed addresses.
"""

from __future__ import annotations

import json
import logging
import re
import secrets

from sqlalchemy import func, select

from hubra.core.extensions import db
from hubra.core.models.managed_mail import ManagedMailAddress

_log = logging.getLogger(__name__)

_PREFIX_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,62}[a-z0-9])?$")


def validate_mail_prefix(prefix: str) -> str:
    """Validate and normalise a mail prefix (local part before @).

    Returns the lowercased, stripped prefix.  Raises ValueError on invalid
    input.
    """
    cleaned = prefix.strip().lower()
    if not cleaned:
        raise ValueError("Mail prefix cannot be empty")
    if not _PREFIX_RE.match(cleaned):
        raise ValueError(
            "Mail prefix must be 1-64 chars, alphanumeric with hyphens/dots, "
            "starting and ending with alphanumeric"
        )
    return cleaned


def normalize_prefix_from_name(name: str) -> str:
    """Derive a mail prefix from a group/function display name."""
    cleaned = name.lower().strip()
    cleaned = (
        cleaned.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    cleaned = re.sub(r"[^a-z0-9]+", "", cleaned)
    return cleaned or "mail"


def resolve_alias_targets(addr: ManagedMailAddress) -> list[str]:
    """Resolve forward targets for a ManagedMailAddress.

    If ``fixed_forward_targets`` is set, those are used directly.
    For alias MMAs (owner_type='mail_address'), look up parent address.
    For members: forward to private email (if verified and enabled).
    For system mailboxes: no forwarding (return empty).
    For groups/functions: resolve from members/holders, fall back to postmaster.
    """
    if addr.fixed_forward_targets:
        try:
            return json.loads(addr.fixed_forward_targets)
        except (json.JSONDecodeError, TypeError):
            pass

    if addr.owner_type == "mail_address" and addr.owner_id is not None:
        parent = db.session.get(ManagedMailAddress, addr.owner_id)
        if parent:
            return [parent.address]
        return []

    if addr.owner_type == "member" and addr.owner_id is not None:
        from hubra.core.services.mail_provisioning import (
            _resolve_member_forward_targets,
        )

        return _resolve_member_forward_targets(addr)

    if addr.is_system:
        return []

    from hubra.core.models.member import Member, member_groups
    from hubra.core.models.function import FunctionHolder

    targets: list[str | None] = []

    if addr.owner_type == "group" and addr.owner_id is not None:
        targets = list(
            db.session.scalars(
                select(Member.public_email)
                .join(member_groups, Member.id == member_groups.c.member_id)
                .where(member_groups.c.group_id == addr.owner_id)
                .where(Member.archived_at.is_(None))
                .where(Member.public_email.isnot(None))
            ).all()
        )
    elif addr.owner_type == "function" and addr.owner_id is not None:
        targets = list(
            db.session.scalars(
                select(Member.public_email)
                .join(FunctionHolder, FunctionHolder.member_id == Member.id)
                .where(FunctionHolder.function_id == addr.owner_id)
                .where(Member.archived_at.is_(None))
                .where(Member.public_email.isnot(None))
            ).all()
        )

    targets = [t for t in targets if t]

    if not targets:
        domain = _get_club_domain()
        postmaster = f"postmaster@{domain}" if domain else None
        if postmaster and postmaster != addr.address:
            targets = [postmaster]

    return targets  # type: ignore[return-value]  # filtered None above


def resolve_postmaster_targets() -> list[str]:
    """Resolve forward targets for the postmaster address specifically.

    Postmaster forwards to Vorstand group members, falling back to the
    first admin member's private email.
    """
    from hubra.core.models.member import Member, member_groups
    from hubra.core.models.group import Group

    vorstand = db.session.scalar(
        select(Group).where(Group.name == "Vorstand").where(Group.archived_at.is_(None))
    )
    if vorstand is not None:
        targets = list(
            db.session.scalars(
                select(Member.public_email)
                .join(member_groups, Member.id == member_groups.c.member_id)
                .where(member_groups.c.group_id == vorstand.id)
                .where(Member.archived_at.is_(None))
                .where(Member.public_email.isnot(None))
            ).all()
        )
        targets = [t for t in targets if t]
        if targets:
            return targets  # type: ignore[return-value]

    from hubra.core.models.role import Role
    from hubra.core.models.member import member_roles

    admin = db.session.scalar(
        select(Member)
        .join(member_roles, member_roles.c.member_id == Member.id)
        .join(Role, member_roles.c.role_id == Role.id)
        .where(Role.is_admin.is_(True))
        .where(Member.archived_at.is_(None))
        .order_by(Member.id)
    )
    if admin and admin.email:
        return [admin.email]

    return []


def _get_club_domain() -> str:
    from hubra.api.settings.services import SettingService

    return SettingService.get("mail.domain", default="") or ""


def owns_mail_address(address: str) -> bool:
    """Whether *address* belongs to this club.

    Every club's mailboxes and aliases live on one shared mail server, so a
    club may only see or change addresses in its own mail domain, and not
    in a domain another club has verified.
    """
    from hubra.core.models.domain import Domain
    from hubra.core.tenant.context import current_tenant

    domain = _get_club_domain().strip().lower()
    _local, at, addr_domain = (address or "").strip().lower().rpartition("@")
    if not domain or not at or addr_domain != domain:
        return False
    tenant = current_tenant()
    claimed = db.session.scalar(
        select(Domain.tenant_id).where(
            func.lower(Domain.domain) == domain, Domain.verified.is_(True)
        )
    )
    return claimed is None or (tenant is not None and claimed == tenant.id)


def require_own_mail_address(address: str) -> None:
    """Refuse an address outside this club's mail domain (see owns_mail_address)."""
    from hubra.core.errors import raise_error

    if not owns_mail_address(address):
        raise_error(
            400,
            "VALIDATION_ERROR",
            f"{address} is not in this club's mail domain",
        )


def sync_alias(addr: ManagedMailAddress) -> None:
    """Create or update the WildDuck forwarding alias for *addr*.

    If ``is_enabled`` is False, the alias targets are set to ``[]`` in
    WildDuck (mail queues, nothing forwarded).  Otherwise targets are
    resolved normally.
    """
    from hubra.core.services.wildduck import WildDuckError, try_get_client

    wd = try_get_client()
    if wd is None:
        addr.provisioning_status = "sync_failed"
        _log.debug("sync_alias: WildDuck not configured, skipping %s", addr.address)
        return

    if addr.address == f"postmaster@{_get_club_domain()}":
        targets = resolve_postmaster_targets()
    else:
        targets = resolve_alias_targets(addr)

    if not addr.is_enabled:
        targets = []

    try:
        if addr.wildduck_id is None:
            result = wd.create_forwarding_alias(
                addr.address, targets, name=addr.address
            )
            addr.wildduck_id = result.get("id")
            _log.info(
                "sync_alias: created alias %s (%d targets)",
                addr.address,
                len(targets),
            )
        else:
            wd.update_forwarding_alias(addr.wildduck_id, targets)
            _log.info(
                "sync_alias: updated alias %s (%d targets)",
                addr.address,
                len(targets),
            )
        addr.provisioning_status = "provisioned"
    except WildDuckError as exc:
        addr.provisioning_status = "sync_failed"
        _log.warning("sync_alias: WildDuck error for %s: %s", addr.address, exc)

    _sync_child_aliases(addr, targets if addr.is_enabled else [])


def _sync_child_aliases(addr: ManagedMailAddress, targets: list[str]) -> None:
    """Sync WildDuck targets for all alias MMA rows belonging to *addr*."""
    from hubra.core.services.wildduck import WildDuckError, try_get_client

    child_aliases = list(
        db.session.scalars(
            select(ManagedMailAddress).where(
                ManagedMailAddress.owner_type == "mail_address",
                ManagedMailAddress.owner_id == addr.id,
            )
        ).all()
    )
    if not child_aliases:
        return

    wd = try_get_client()
    if wd is None:
        return

    effective_targets = targets if addr.is_enabled else []
    for child in child_aliases:
        try:
            if child.wildduck_id is None:
                result = wd.create_forwarding_alias(
                    child.address, effective_targets, name=child.address
                )
                child.wildduck_id = result.get("id")
                child.provisioning_status = "provisioned"
            else:
                wd.update_forwarding_alias(child.wildduck_id, effective_targets)
                child.provisioning_status = "provisioned"
        except WildDuckError as exc:
            child.provisioning_status = "sync_failed"
            _log.warning(
                "sync_child_aliases: WildDuck error for %s: %s",
                child.address,
                exc,
            )


def deprovision_alias(addr: ManagedMailAddress) -> None:
    """Delete the WildDuck alias for *addr* and all child alias MMAs."""
    from hubra.core.services.wildduck import WildDuckError, try_get_client

    wd = try_get_client()

    child_aliases = list(
        db.session.scalars(
            select(ManagedMailAddress).where(
                ManagedMailAddress.owner_type == "mail_address",
                ManagedMailAddress.owner_id == addr.id,
            )
        ).all()
    )
    if wd is not None:
        for child in child_aliases:
            if child.wildduck_id:
                try:
                    wd.delete_forwarding_alias(child.wildduck_id)
                except WildDuckError as exc:
                    _log.warning(
                        "deprovision_alias: child alias %s: %s", child.address, exc
                    )

    if addr.wildduck_id is not None:
        if wd is not None:
            try:
                wd.delete_forwarding_alias(addr.wildduck_id)
                _log.info("deprovision_alias: deleted alias %s", addr.address)
            except WildDuckError as exc:
                _log.warning(
                    "deprovision_alias: WildDuck error for %s: %s", addr.address, exc
                )

    addr.wildduck_id = None
    addr.provisioning_status = "pending"


def sync_mailbox_forward(addr: ManagedMailAddress, forward_to: str | None) -> None:
    """Create/update/delete the forward filter on a mailbox-type address.

    If *forward_to* is None, the filter is removed (forwarding disabled).
    """
    from hubra.core.services.wildduck import WildDuckError, try_get_client

    if addr.wildduck_user_id is None:
        return

    wd = try_get_client()
    if wd is None:
        addr.provisioning_status = "sync_failed"
        return

    try:
        if forward_to is None:
            if addr.wildduck_filter_id:
                wd.delete_forward_filter(addr.wildduck_user_id, addr.wildduck_filter_id)
                addr.wildduck_filter_id = None
                _log.info("sync_mailbox_forward: removed filter for %s", addr.address)
        else:
            if addr.wildduck_filter_id:
                wd.delete_forward_filter(addr.wildduck_user_id, addr.wildduck_filter_id)
            result = wd.create_forward_filter(addr.wildduck_user_id, forward_to)
            addr.wildduck_filter_id = result.get("id")
            _log.info(
                "sync_mailbox_forward: created filter for %s → %s",
                addr.address,
                forward_to,
            )
        addr.provisioning_status = "provisioned"
    except WildDuckError as exc:
        addr.provisioning_status = "sync_failed"
        _log.warning(
            "sync_mailbox_forward: WildDuck error for %s: %s", addr.address, exc
        )


def toggle_mail_enabled(addr: ManagedMailAddress, enabled: bool) -> None:
    """Enable or disable mail for *addr*.

    For new-style group MMAs (kind=group): uses ensure_absent / ensure_mailbox+
    ensure_forwarding primitives.

    For legacy MMAs: uses the old WildDuck alias targets approach.
    """
    if enabled == addr.is_enabled:
        return

    if addr.kind in ("group", "function", "member"):
        from hubra.core.services.mail_provisioning import (
            ensure_absent,
            ensure_alias,
            ensure_forwarding,
            ensure_mailbox,
            _resolve_group_member_targets,
            _resolve_function_holder_targets,
            _resolve_member_forward_targets,
        )

        if not enabled:
            ensure_absent(addr)
            addr.is_enabled = False
            addr.enabled = False
        else:
            addr.is_enabled = True
            addr.enabled = True
            if addr.address_type == "mailbox":
                if addr.kind == "member":
                    from hubra.core.models.member import Member

                    member = db.session.get(Member, addr.owner_id)
                    pwd = member.password_hash if member else None
                    ensure_mailbox(addr, password_hash=pwd)
                    ensure_alias(addr)
                    targets = _resolve_member_forward_targets(addr)
                    ensure_forwarding(addr, targets)
                elif addr.kind == "group":
                    ensure_mailbox(addr)
                    ensure_alias(addr)
                    targets = _resolve_group_member_targets(addr.owner_id or 0)
                    ensure_forwarding(addr, targets)
                else:
                    ensure_mailbox(addr)
                    ensure_alias(addr)
                    targets = _resolve_function_holder_targets(addr.owner_id or 0)
                    ensure_forwarding(addr, targets)
            else:
                ensure_alias(addr)
        return

    if addr.address_type == "alias":
        from hubra.core.services.wildduck import WildDuckError, try_get_client

        if not enabled:
            targets = resolve_alias_targets(addr)
            addr.cached_forward_targets = json.dumps(targets)
            addr.is_enabled = False

            wd = try_get_client()
            if wd is not None and addr.wildduck_id:
                try:
                    wd.update_forwarding_alias(addr.wildduck_id, [])
                    _log.info("toggle_mail_enabled: disabled alias %s", addr.address)
                except WildDuckError as exc:
                    _log.warning(
                        "toggle_mail_enabled: WildDuck error disabling %s: %s",
                        addr.address,
                        exc,
                    )

            _sync_child_aliases(addr, [])
        else:
            cached = addr.cached_forward_targets
            targets = json.loads(cached) if cached else resolve_alias_targets(addr)
            addr.cached_forward_targets = None
            addr.is_enabled = True

            wd = try_get_client()
            if wd is not None:
                if addr.wildduck_id:
                    try:
                        wd.update_forwarding_alias(addr.wildduck_id, targets)
                    except WildDuckError as exc:
                        _log.warning(
                            "toggle_mail_enabled: WildDuck error enabling %s: %s",
                            addr.address,
                            exc,
                        )
                else:
                    try:
                        result = wd.create_forwarding_alias(
                            addr.address, targets, name=addr.address
                        )
                        addr.wildduck_id = result.get("id")
                    except WildDuckError as exc:
                        _log.warning(
                            "toggle_mail_enabled: WildDuck error creating %s: %s",
                            addr.address,
                            exc,
                        )

            _sync_child_aliases(addr, targets)

    elif addr.address_type == "mailbox":
        addr.is_enabled = enabled
        if enabled:
            if addr.fixed_forward_targets:
                targets = json.loads(addr.fixed_forward_targets)
                forward_to = targets[0] if targets else None
            elif addr.owner_id is not None:
                from hubra.core.models.member import Member

                member = db.session.get(Member, addr.owner_id)
                forward_to = member.email if member else None
            else:
                forward_to = f"postmaster@{_get_club_domain()}"
            sync_mailbox_forward(addr, forward_to)
        else:
            sync_mailbox_forward(addr, None)


def change_mail_prefix(addr: ManagedMailAddress, new_prefix: str, domain: str) -> None:
    """Change the mail prefix (local part) of *addr*.

    For new-style group MMAs (kind=group): uses resolve_local_part for
    normalization and collision suffixing, then re-provisions via the
    new primitives.

    For legacy MMAs: uses the old WildDuck alias swap approach.
    """
    from hubra.core.services.mail_provisioning import resolve_local_part

    if addr.kind in ("group", "function", "member"):
        from hubra.core.services.mail_provisioning import (
            ensure_absent,
            ensure_alias,
            ensure_forwarding,
            ensure_mailbox,
            _resolve_group_member_targets,
            _resolve_function_holder_targets,
            _resolve_member_forward_targets,
        )

        local = resolve_local_part(new_prefix)
        new_address = f"{local}@{domain}"
        if new_address == addr.address:
            return

        existing = db.session.scalar(
            select(ManagedMailAddress).where(ManagedMailAddress.address == new_address)
        )
        if existing is not None and existing.id != addr.id:
            raise ValueError(f"Address {new_address} is already in use")

        ensure_absent(addr)

        old_enabled = addr.is_enabled
        addr.address = new_address
        addr.mail_prefix = local
        addr.local_part = local
        addr.domain = domain

        if old_enabled:
            if addr.address_type == "mailbox":
                if addr.kind == "member":
                    from hubra.core.models.member import Member

                    member = db.session.get(Member, addr.owner_id)
                    pwd = member.password_hash if member else None
                    ensure_mailbox(addr, password_hash=pwd)
                    ensure_alias(addr)
                    targets = _resolve_member_forward_targets(addr)
                    ensure_forwarding(addr, targets)
                elif addr.kind == "group":
                    ensure_mailbox(addr)
                    ensure_alias(addr)
                    targets = _resolve_group_member_targets(addr.owner_id or 0)
                    ensure_forwarding(addr, targets)
                else:
                    ensure_mailbox(addr)
                    ensure_alias(addr)
                    targets = _resolve_function_holder_targets(addr.owner_id or 0)
                    ensure_forwarding(addr, targets)
            else:
                ensure_alias(addr)
        return

    from hubra.core.services.wildduck import WildDuckError, try_get_client

    prefix = validate_mail_prefix(new_prefix)
    new_address = f"{prefix}@{domain}"

    if new_address == addr.address:
        return

    existing = db.session.scalar(
        select(ManagedMailAddress).where(ManagedMailAddress.address == new_address)
    )
    if existing is not None:
        raise ValueError(f"Address {new_address} is already in use")

    old_alias_id = addr.wildduck_id
    old_address = addr.address

    targets = resolve_alias_targets(addr)
    if not addr.is_enabled:
        targets = []

    wd = try_get_client()
    if wd is not None:
        try:
            result = wd.create_forwarding_alias(new_address, targets, name=new_address)
            addr.wildduck_id = result.get("id")
            addr.provisioning_status = "provisioned"
            _log.info(
                "change_mail_prefix: created new alias %s (was %s)",
                new_address,
                old_address,
            )
        except WildDuckError as exc:
            _log.warning(
                "change_mail_prefix: WildDuck error creating %s: %s",
                new_address,
                exc,
            )
            addr.provisioning_status = "sync_failed"

        if old_alias_id:
            try:
                wd.delete_forwarding_alias(old_alias_id)
                _log.info("change_mail_prefix: deleted old alias %s", old_address)
            except WildDuckError as exc:
                _log.warning(
                    "change_mail_prefix: WildDuck error deleting old %s: %s",
                    old_address,
                    exc,
                )

    addr.address = new_address
    addr.mail_prefix = prefix

    _sync_child_aliases(addr, targets)


def get_system_addresses() -> list[ManagedMailAddress]:
    """Return all system ManagedMailAddress rows ordered by address."""
    return list(
        db.session.scalars(
            select(ManagedMailAddress)
            .where(ManagedMailAddress.is_system.is_(True))
            .order_by(ManagedMailAddress.address)
        ).all()
    )


def create_system_address(
    address: str,
    address_type: str,
    display_name: str | None = None,
    forward_targets: list[str] | None = None,
    is_protected: bool = False,
    domain: str = "",
) -> ManagedMailAddress:
    """Create a system ManagedMailAddress.

    For mailbox type with forward_targets, sets fixed_forward_targets and
    creates a forward filter.  For alias type, provisions a WildDuck
    forwarding alias.
    """
    from hubra.core.services.wildduck import WildDuckError, try_get_client

    prefix = address.split("@")[0] if "@" in address else address
    if not prefix and domain:
        address = f"{prefix}@{domain}"
    elif "@" not in address and domain:
        address = f"{address}@{domain}"

    if not owns_mail_address(address):
        raise ValueError(f"{address} is not in this club's mail domain")

    existing = db.session.scalar(
        select(ManagedMailAddress).where(ManagedMailAddress.address == address)
    )
    if existing is not None:
        raise ValueError(f"Address {address} already exists")

    addr = ManagedMailAddress(
        address=address,
        address_type=address_type,
        is_protected=is_protected,
        is_enabled=True,
        is_system=True,
        mail_prefix=prefix,
        display_name=display_name,
        fixed_forward_targets=json.dumps(forward_targets) if forward_targets else None,
        provisioning_status="pending",
        kind="system",
        local_part=prefix,
        domain=domain or _get_club_domain(),
    )
    db.session.add(addr)
    db.session.flush()

    wd = try_get_client()
    if wd is not None:
        if address_type == "alias":
            targets = forward_targets or []
            if not targets:
                targets = resolve_alias_targets(addr)
            try:
                result = wd.create_forwarding_alias(address, targets, name=address)
                addr.wildduck_id = result.get("id")
                addr.provisioning_status = "provisioned"
            except WildDuckError as exc:
                addr.provisioning_status = "sync_failed"
                _log.warning(
                    "create_system_address: WildDuck error for %s: %s", address, exc
                )
        elif address_type == "mailbox" and forward_targets:
            from hubra.core.services.wildduck import WildDuckError as _WDE

            try:
                result = wd.create_user(
                    username=prefix,
                    name=display_name or prefix,
                    password=secrets.token_urlsafe(32),
                    quota_mb=512,
                )
                addr.wildduck_user_id = result.get("id")
                fwd = forward_targets[0] if forward_targets else None
                user_id = addr.wildduck_user_id
                if fwd and user_id:
                    filter_result = wd.create_forward_filter(user_id, fwd)
                    addr.wildduck_filter_id = filter_result.get("id")
                addr.provisioning_status = "provisioned"
            except _WDE as exc:
                addr.provisioning_status = "sync_failed"
                _log.warning(
                    "create_system_address: WildDuck error for %s: %s", address, exc
                )

    return addr


def delete_system_address(addr: ManagedMailAddress) -> None:
    """Delete a system ManagedMailAddress.

    Raises PermissionError if the address is protected.
    """
    if addr.is_protected:
        raise PermissionError(f"Cannot delete protected system address {addr.address}")

    from hubra.core.services.mail_provisioning import ensure_absent

    ensure_absent(addr)
    db.session.delete(addr)


def get_or_create_for_group(
    group_id: int, prefix: str, domain: str
) -> ManagedMailAddress:
    """Get or create an alias-backed ManagedMailAddress for a group.

    The primary group alias is a pure forwarding alias (no stored copy) that
    forwards to ALL current members via WildDuck ``/addresses/forwarded``.
    """
    existing = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "group",
            ManagedMailAddress.owner_id == group_id,
            ManagedMailAddress.fixed_forward_targets.is_(None),
        )
    )
    if existing is not None:
        local = prefix.strip().lower()
        address = f"{local}@{domain}"
        existing.address_type = "alias"
        existing.mail_prefix = local
        existing.address = address
        existing.kind = "group"
        existing.local_part = local
        existing.domain = domain
        existing.owner_type = "group"
        existing.owner_id = group_id
        existing.enabled = True
        return existing

    from hubra.core.services.mail_provisioning import resolve_local_part

    local = resolve_local_part(prefix)
    address = f"{local}@{domain}"

    addr = ManagedMailAddress(
        address=address,
        address_type="alias",
        is_protected=True,
        is_enabled=True,
        mail_prefix=local,
        kind="group",
        local_part=local,
        domain=domain,
        owner_type="group",
        owner_id=group_id,
        enabled=True,
    )
    db.session.add(addr)
    db.session.flush()
    return addr


def get_or_create_group_additional_alias(
    group_id: int, prefix: str, domain: str, actor_id: int | None = None
) -> ManagedMailAddress:
    """Create an additional alias MMA for a group.

    Additional group aliases are non-mailbox-backed and forward to the
    primary group alias address (not directly to members).
    """
    from hubra.core.services.mail_provisioning import resolve_local_part

    local = resolve_local_part(prefix)
    address = f"{local}@{domain}"

    existing = db.session.scalar(
        select(ManagedMailAddress).where(ManagedMailAddress.address == address)
    )
    if existing is not None:
        raise ValueError(f"Address {address} is already in use")

    primary = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "group",
            ManagedMailAddress.owner_id == group_id,
            ManagedMailAddress.fixed_forward_targets.is_(None),
        )
    )
    primary_address = primary.address if primary else None
    fixed_targets = json.dumps([primary_address]) if primary_address else None

    addr = ManagedMailAddress(
        address=address,
        address_type="alias",
        is_protected=False,
        is_enabled=True,
        mail_prefix=local,
        kind="group",
        local_part=local,
        domain=domain,
        owner_type="group",
        owner_id=group_id,
        enabled=True,
        fixed_forward_targets=fixed_targets,
    )
    db.session.add(addr)
    db.session.flush()
    return addr


def delete_group_additional_alias(alias_id: int) -> None:
    """Deprovision and delete an additional group alias MMA."""
    from hubra.core.services.mail_provisioning import ensure_absent

    addr = db.session.get(ManagedMailAddress, alias_id)
    if addr is None:
        return
    ensure_absent(addr)
    db.session.delete(addr)


def get_or_create_for_function(
    function_id: int, prefix: str, domain: str
) -> ManagedMailAddress:
    """Get or create an alias ManagedMailAddress for a function.

    The primary function alias forwards to ALL current holders via the
    user ``targets`` array.
    """
    existing = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "function",
            ManagedMailAddress.owner_id == function_id,
            ManagedMailAddress.fixed_forward_targets.is_(None),
        )
    )
    if existing is not None:
        local = prefix.strip().lower()
        address = f"{local}@{domain}"
        existing.address_type = "alias"
        existing.mail_prefix = local
        existing.address = address
        existing.kind = "function"
        existing.local_part = local
        existing.domain = domain
        existing.owner_type = "function"
        existing.owner_id = function_id
        existing.enabled = True
        return existing

    from hubra.core.services.mail_provisioning import resolve_local_part

    local = resolve_local_part(prefix)
    address = f"{local}@{domain}"

    addr = ManagedMailAddress(
        address=address,
        address_type="alias",
        is_protected=True,
        is_enabled=True,
        mail_prefix=local,
        kind="function",
        local_part=local,
        domain=domain,
        owner_type="function",
        owner_id=function_id,
        enabled=True,
    )
    db.session.add(addr)
    db.session.flush()
    return addr


def get_or_create_function_additional_alias(
    function_id: int, prefix: str, domain: str, actor_id: int | None = None
) -> ManagedMailAddress:
    """Create an additional alias MMA for a function.

    Additional function aliases are non-mailbox-backed and forward to the
    primary function alias address (not directly to holders).
    """
    from hubra.core.services.mail_provisioning import resolve_local_part

    local = resolve_local_part(prefix)
    address = f"{local}@{domain}"

    existing = db.session.scalar(
        select(ManagedMailAddress).where(ManagedMailAddress.address == address)
    )
    if existing is not None:
        raise ValueError(f"Address {address} is already in use")

    primary = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "function",
            ManagedMailAddress.owner_id == function_id,
            ManagedMailAddress.fixed_forward_targets.is_(None),
        )
    )
    primary_address = primary.address if primary else None
    fixed_targets = json.dumps([primary_address]) if primary_address else None

    addr = ManagedMailAddress(
        address=address,
        address_type="alias",
        is_protected=False,
        is_enabled=True,
        mail_prefix=local,
        kind="function",
        local_part=local,
        domain=domain,
        owner_type="function",
        owner_id=function_id,
        enabled=True,
        fixed_forward_targets=fixed_targets,
    )
    db.session.add(addr)
    db.session.flush()
    return addr


def delete_function_additional_alias(alias_id: int) -> None:
    """Deprovision and delete an additional function alias MMA."""
    from hubra.core.services.mail_provisioning import ensure_absent

    addr = db.session.get(ManagedMailAddress, alias_id)
    if addr is None:
        return
    ensure_absent(addr)
    db.session.delete(addr)


def remove_for_group(group_id: int) -> None:
    """Deprovision and remove all ManagedMailAddress rows linked to a group."""
    from hubra.core.services.binding_engine import (
        assert_source_deletable,
        cascade_delete_disabled,
    )
    from hubra.core.services.mail_provisioning import ensure_absent

    addrs = list(
        db.session.scalars(
            select(ManagedMailAddress).where(
                ManagedMailAddress.owner_type == "group",
                ManagedMailAddress.owner_id == group_id,
            )
        ).all()
    )
    for addr in addrs:
        assert_source_deletable("mail_address", str(addr.id))
        _delete_aliases_for_mma(addr)
        ensure_absent(addr)
        cascade_delete_disabled("mail_address", str(addr.id))
        db.session.delete(addr)


def remove_for_function(function_id: int) -> None:
    """Deprovision and remove ManagedMailAddress rows linked to a function."""
    from hubra.core.services.binding_engine import (
        assert_source_deletable,
        cascade_delete_disabled,
    )
    from hubra.core.services.mail_provisioning import ensure_absent

    addrs = list(
        db.session.scalars(
            select(ManagedMailAddress).where(
                ManagedMailAddress.owner_type == "function",
                ManagedMailAddress.owner_id == function_id,
            )
        ).all()
    )
    for addr in addrs:
        assert_source_deletable("mail_address", str(addr.id))
        _delete_aliases_for_mma(addr)
        ensure_absent(addr)
        cascade_delete_disabled("mail_address", str(addr.id))
        db.session.delete(addr)


def _delete_aliases_for_mma(addr: ManagedMailAddress) -> None:
    """Delete all alias MMA rows belonging to *addr* (with WildDuck cleanup)."""
    child_aliases = list(
        db.session.scalars(
            select(ManagedMailAddress).where(
                ManagedMailAddress.owner_type == "mail_address",
                ManagedMailAddress.owner_id == addr.id,
            )
        ).all()
    )
    from hubra.core.services.mail_provisioning import ensure_absent

    for child in child_aliases:
        ensure_absent(child)
        db.session.delete(child)


def get_or_create_for_member(
    member_id: int, prefix: str, domain: str
) -> ManagedMailAddress:
    """Get or create a mailbox-backed ManagedMailAddress for a member.

    The member mailbox is the MASTER copy (1 GB quota, retention OFF by
    default). Uses resolve_local_part for normalization + collision
    handling.
    """
    existing = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "member",
            ManagedMailAddress.owner_id == member_id,
        )
    )
    if existing is not None:
        local = prefix.strip().lower()
        address = f"{local}@{domain}"
        existing.address_type = "mailbox"
        existing.mail_prefix = local
        existing.address = address
        existing.kind = "member"
        existing.local_part = local
        existing.domain = domain
        existing.owner_type = "member"
        existing.owner_id = member_id
        if existing.enabled is None:
            existing.enabled = True
        if existing.quota_bytes is None:
            existing.quota_bytes = 1024 * 1024 * 1024
        if existing.retention is None:
            existing.retention = None
        return existing

    from hubra.core.services.mail_provisioning import resolve_local_part

    local = resolve_local_part(prefix)
    address = f"{local}@{domain}"

    addr = ManagedMailAddress(
        address=address,
        address_type="mailbox",
        is_protected=False,
        is_enabled=True,
        mail_prefix=local,
        kind="member",
        local_part=local,
        domain=domain,
        owner_type="member",
        owner_id=member_id,
        enabled=True,
        quota_bytes=1024 * 1024 * 1024,
        retention=None,
    )
    db.session.add(addr)
    db.session.flush()
    return addr


def deprovision_mailbox(addr: ManagedMailAddress) -> None:
    """Delete the WildDuck user (mailbox) for *addr*."""
    from hubra.core.services.wildduck import WildDuckError, try_get_client

    if addr.wildduck_user_id is None:
        return

    wd = try_get_client()
    if wd is None:
        return

    try:
        wd.delete_user(addr.wildduck_user_id)
        _log.info("deprovision_mailbox: deleted user for %s", addr.address)
    except WildDuckError as exc:
        _log.warning(
            "deprovision_mailbox: WildDuck error for %s: %s", addr.address, exc
        )

    addr.wildduck_user_id = None
    addr.wildduck_filter_id = None
    addr.provisioning_status = "pending"


def remove_for_member(member_id: int) -> None:
    """Deprovision and remove ManagedMailAddress rows linked to a member.

    Uses ``ensure_absent`` (new-generation primitive) instead of the old
    ``deprovision_mailbox``. This is for permanent deletion — for archive,
    use ``disable_member_mail`` instead.
    """
    from hubra.core.services.binding_engine import (
        assert_source_deletable,
        cascade_delete_disabled,
    )
    from hubra.core.services.mail_provisioning import ensure_absent

    addrs = list(
        db.session.scalars(
            select(ManagedMailAddress).where(
                ManagedMailAddress.owner_type == "member",
                ManagedMailAddress.owner_id == member_id,
            )
        ).all()
    )
    for addr in addrs:
        assert_source_deletable("mail_address", str(addr.id))
        ensure_absent(addr)
        cascade_delete_disabled("mail_address", str(addr.id))
        db.session.delete(addr)


def disable_member_mail(member_id: int) -> None:
    """Disable a member's WildDuck mailbox (archive or disable).

    Sets ``disabled=True`` on the WildDuck user so login is blocked but
    stored mail is retained. The MMA row is kept (not deleted).
    """
    from hubra.core.services.mail_provisioning import _migrate_legacy_id
    from hubra.core.services.wildduck import WildDuckError, try_get_client

    addr = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "member",
            ManagedMailAddress.owner_id == member_id,
        )
    )
    if addr is None:
        return

    _migrate_legacy_id(addr)
    addr.enabled = False
    addr.is_enabled = False

    if not addr.wildduck_id:
        return

    wd = try_get_client()
    if wd is None:
        return

    try:
        wd.update_user_attributes(addr.wildduck_id, disabled=True)
        _log.info(
            "disable_member_mail: disabled WildDuck user for member %d", member_id
        )
    except WildDuckError as exc:
        _log.warning(
            "disable_member_mail: WildDuck error for member %d: %s", member_id, exc
        )


def enable_member_mail(member_id: int, password_hash: str) -> None:
    """Re-enable a member's WildDuck mailbox (unarchive or enable).

    Sets ``disabled=False``, re-pushes the password, and restores
    forwarding if it was previously enabled. The MMA row must already
    exist (it is retained during archive/disable).
    """
    from hubra.core.services.mail_provisioning import (
        _migrate_legacy_id,
        _resolve_member_forward_targets,
        ensure_alias,
        ensure_forwarding,
        ensure_mailbox,
    )
    from hubra.core.services.wildduck import WildDuckError, try_get_client

    addr = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "member",
            ManagedMailAddress.owner_id == member_id,
        )
    )
    if addr is None:
        return

    _migrate_legacy_id(addr)
    addr.enabled = True
    addr.is_enabled = True

    wd = try_get_client()
    if wd is None:
        return

    try:
        if addr.wildduck_id:
            wd.update_user_attributes(addr.wildduck_id, disabled=False)
        ensure_mailbox(addr, password_hash=password_hash)
        ensure_alias(addr)
        targets = _resolve_member_forward_targets(addr)
        ensure_forwarding(addr, targets)
        _log.info("enable_member_mail: enabled WildDuck user for member %d", member_id)
    except WildDuckError as exc:
        _log.warning(
            "enable_member_mail: WildDuck error for member %d: %s", member_id, exc
        )


def _resolve_owner_name(addr: ManagedMailAddress) -> str | None:
    """Resolve a human-readable name for the MMA's owner."""
    if addr.owner_type == "member" and addr.owner_id:
        from hubra.core.models.member import Member

        m = db.session.get(Member, addr.owner_id)
        return m.name if m else None
    if addr.owner_type == "group" and addr.owner_id:
        from hubra.core.models.group import Group

        g = db.session.get(Group, addr.owner_id)
        return g.name if g else None
    if addr.owner_type == "function" and addr.owner_id:
        from hubra.core.models.function import Function

        f = db.session.get(Function, addr.owner_id)
        return f.name if f else None
    return addr.display_name


def serialize(addr: ManagedMailAddress) -> dict:
    cached = None
    if addr.cached_forward_targets:
        try:
            cached = json.loads(addr.cached_forward_targets)
        except (json.JSONDecodeError, TypeError):
            cached = None

    fixed = None
    if addr.fixed_forward_targets:
        try:
            fixed = json.loads(addr.fixed_forward_targets)
        except (json.JSONDecodeError, TypeError):
            fixed = None

    from_whitelist: list[str] = []
    if addr.from_whitelist:
        try:
            parsed = json.loads(addr.from_whitelist)
            if isinstance(parsed, list):
                from_whitelist = [str(x) for x in parsed if isinstance(x, str)]
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "id": addr.id,
        "address": addr.address,
        "addressType": addr.address_type,
        "isProtected": addr.is_protected,
        "forwardingEnabled": addr.forwarding_enabled,
        "isEnabled": addr.is_enabled,
        "isSystem": addr.is_system,
        "mailPrefix": addr.mail_prefix,
        "displayName": addr.display_name,
        "cachedForwardTargets": cached,
        "fixedForwardTargets": fixed,
        "ownerType": addr.owner_type,
        "ownerId": addr.owner_id,
        "linkedGroupId": addr.owner_id if addr.owner_type == "group" else None,
        "linkedFunctionId": addr.owner_id if addr.owner_type == "function" else None,
        "linkedMemberId": addr.owner_id if addr.owner_type == "member" else None,
        "provisioningStatus": addr.provisioning_status,
        "kind": addr.kind,
        "mailboxBacked": addr.address_type == "mailbox",
        "enabled": addr.enabled,
        "forwardEnabled": addr.forward_enabled,
        "localPart": addr.local_part,
        "domain": addr.domain,
        "quotaBytes": addr.quota_bytes,
        "quotaUsed": addr.quota_used,
        "quotaTotal": addr.quota_bytes,
        "retention": addr.retention,
        "fromWhitelist": from_whitelist,
        "wildduckId": addr.wildduck_id,
        "syncState": addr.sync_state,
        "syncError": addr.sync_error,
        "ownerName": _resolve_owner_name(addr),
        "forwardTargets": resolve_alias_targets(addr),
    }


def auto_create_mma_for_group(group_id: int) -> ManagedMailAddress | None:
    """Create a disabled MMA for a group if none exists yet.

    Idempotent — returns the existing MMA if one already exists.
    If an unlinked MMA with the expected address exists (e.g. from a
    seed run where owner_type didn't persist), claims it by setting
    owner_type/owner_id instead of inserting a new row.
    Never raises; logs a warning on failure.
    """
    from hubra.core.models.group import Group

    existing = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "group",
            ManagedMailAddress.owner_id == group_id,
        )
    )
    if existing is not None:
        return existing

    group = db.session.get(Group, group_id)
    if group is None:
        return None

    from hubra.api.settings.services import SettingService

    club_domain = SettingService.get("mail.domain") or ""
    if not club_domain:
        return None
    prefix = normalize_prefix_from_name(group.name)
    from hubra.core.services.mail_provisioning import resolve_local_part

    local = resolve_local_part(prefix)
    address = f"{local}@{club_domain}"

    unlinked = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.address == address,
            ManagedMailAddress.owner_type.is_(None),
        )
    )
    if unlinked is not None:
        unlinked.owner_type = "group"
        unlinked.owner_id = group_id
        unlinked.kind = "group"
        unlinked.enabled = False
        unlinked.is_enabled = False
        unlinked.address_type = "alias"
        unlinked.is_protected = True
        unlinked.mail_prefix = local
        unlinked.local_part = local
        unlinked.domain = club_domain
        db.session.flush()
        _log.info(
            "auto_create_mma_for_group: claimed unlinked MMA %d for group %d",
            unlinked.id,
            group_id,
        )
        return unlinked

    try:
        addr = ManagedMailAddress(
            address=address,
            address_type="alias",
            is_protected=True,
            is_enabled=False,
            mail_prefix=local,
            kind="group",
            local_part=local,
            domain=club_domain,
            owner_type="group",
            owner_id=group_id,
            enabled=False,
        )
        db.session.add(addr)
        db.session.flush()
        _log.info(
            "auto_create_mma_for_group: created disabled MMA for group %d", group_id
        )
        return addr
    except Exception:
        db.session.rollback()
        _log.warning(
            "auto_create_mma_for_group: failed for group %d", group_id, exc_info=True
        )
        return None


def auto_create_mma_for_function(function_id: int) -> ManagedMailAddress | None:
    """Create a disabled MMA for a function if none exists yet.

    Idempotent — returns the existing MMA if one already exists.
    If an unlinked MMA with the expected address exists (e.g. from a
    seed run where owner_type didn't persist), claims it by setting
    owner_type/owner_id instead of inserting a new row.
    Never raises; logs a warning on failure.
    """
    from hubra.core.models.function import Function

    existing = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "function",
            ManagedMailAddress.owner_id == function_id,
        )
    )
    if existing is not None:
        return existing

    fn = db.session.get(Function, function_id)
    if fn is None:
        return None

    from hubra.api.settings.services import SettingService

    club_domain = SettingService.get("mail.domain") or ""
    if not club_domain:
        return None
    prefix = normalize_prefix_from_name(fn.name)
    from hubra.core.services.mail_provisioning import resolve_local_part

    local = resolve_local_part(prefix)
    address = f"{local}@{club_domain}"

    unlinked = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.address == address,
            ManagedMailAddress.owner_type.is_(None),
        )
    )
    if unlinked is not None:
        unlinked.owner_type = "function"
        unlinked.owner_id = function_id
        unlinked.kind = "function"
        unlinked.enabled = False
        unlinked.is_enabled = False
        unlinked.address_type = "alias"
        unlinked.is_protected = True
        unlinked.mail_prefix = local
        unlinked.local_part = local
        unlinked.domain = club_domain
        db.session.flush()
        _log.info(
            "auto_create_mma_for_function: claimed unlinked MMA %d for function %d",
            unlinked.id,
            function_id,
        )
        return unlinked

    try:
        addr = ManagedMailAddress(
            address=address,
            address_type="alias",
            is_protected=True,
            is_enabled=False,
            mail_prefix=local,
            kind="function",
            local_part=local,
            domain=club_domain,
            owner_type="function",
            owner_id=function_id,
            enabled=False,
        )
        db.session.add(addr)
        db.session.flush()
        _log.info(
            "auto_create_mma_for_function: created disabled MMA for function %d",
            function_id,
        )
        return addr
    except Exception:
        db.session.rollback()
        _log.warning(
            "auto_create_mma_for_function: failed for function %d",
            function_id,
            exc_info=True,
        )
        return None


def auto_create_mma_for_member(member_id: int) -> ManagedMailAddress | None:
    """Create an enabled MMA for a member if none exists yet.

    Idempotent — returns the existing MMA if one already exists.
    Never raises; logs a warning on failure.
    """
    from hubra.core.models.member import Member

    existing = db.session.scalar(
        select(ManagedMailAddress).where(
            ManagedMailAddress.owner_type == "member",
            ManagedMailAddress.owner_id == member_id,
        )
    )
    if existing is not None:
        return existing

    member = db.session.get(Member, member_id)
    if member is None:
        return None

    from hubra.api.settings.services import SettingService

    club_domain = SettingService.get("mail.domain") or ""
    if not club_domain:
        return None

    prefix = member.public_email.split("@")[0] if member.public_email else member.name
    from hubra.core.services.mail_provisioning import resolve_local_part

    local = resolve_local_part(prefix)
    address = f"{local}@{club_domain}"

    try:
        addr = ManagedMailAddress(
            address=address,
            address_type="mailbox",
            is_protected=False,
            is_enabled=True,
            mail_prefix=local,
            kind="member",
            local_part=local,
            domain=club_domain,
            owner_type="member",
            owner_id=member_id,
            enabled=True,
            quota_bytes=1024 * 1024 * 1024,
            retention=None,
        )
        db.session.add(addr)
        db.session.flush()
        _log.info("auto_create_mma_for_member: created MMA for member %d", member_id)
        return addr
    except Exception:
        db.session.rollback()
        _log.warning(
            "auto_create_mma_for_member: failed for member %d", member_id, exc_info=True
        )
        return None


# ── Unified address management ────────────────────────────────────────────────


def list_addresses(
    *,
    owner_type: str | None = None,
    enabled: bool | None = None,
    sync_state: str | None = None,
    search: str | None = None,
    include_system: bool = False,
) -> list[dict]:
    """List MMAs with optional filters. Excludes system by default."""
    stmt = select(ManagedMailAddress).order_by(ManagedMailAddress.address)
    if not include_system:
        stmt = stmt.where(ManagedMailAddress.is_system.is_(False))
    if owner_type:
        stmt = stmt.where(ManagedMailAddress.owner_type == owner_type)
    if enabled is not None:
        stmt = stmt.where(ManagedMailAddress.is_enabled == enabled)
    if sync_state:
        stmt = stmt.where(ManagedMailAddress.sync_state == sync_state)
    if search:
        stmt = stmt.where(ManagedMailAddress.address.ilike(f"%{search}%"))
    return [serialize(a) for a in db.session.scalars(stmt).all()]


def get_address(mma_id: int) -> dict | None:
    addr = db.session.get(ManagedMailAddress, mma_id)
    if addr is None:
        return None
    return serialize(addr)


def toggle_address(mma_id: int, enabled: bool) -> dict | None:
    addr = db.session.get(ManagedMailAddress, mma_id)
    if addr is None:
        return None
    toggle_mail_enabled(addr, enabled)
    return serialize(addr)


def change_address_prefix(mma_id: int, prefix: str, domain: str) -> dict | None:
    addr = db.session.get(ManagedMailAddress, mma_id)
    if addr is None:
        return None
    change_mail_prefix(addr, prefix, domain)
    return serialize(addr)


def update_address(mma_id: int, **fields) -> dict | None:
    addr = db.session.get(ManagedMailAddress, mma_id)
    if addr is None:
        return None
    if "forwarding_enabled" in fields:
        addr.forwarding_enabled = fields["forwarding_enabled"]
    if "retention_ms" in fields:
        addr.retention = fields["retention_ms"]
    if "quota_bytes" in fields:
        addr.quota_bytes = fields["quota_bytes"]
    db.session.flush()
    return serialize(addr)


def list_aliases(mma_id: int) -> list[dict]:
    """List additional aliases (MMA rows with owner_type='mail_address')."""
    aliases = list(
        db.session.scalars(
            select(ManagedMailAddress)
            .where(ManagedMailAddress.owner_type == "mail_address")
            .where(ManagedMailAddress.owner_id == mma_id)
            .order_by(ManagedMailAddress.address)
        ).all()
    )
    return [serialize(a) for a in aliases]


def create_alias(
    parent_mma_id: int, prefix: str, domain: str, actor_id: int | None = None
) -> ManagedMailAddress:
    """Create an additional alias for any MMA (group, function, member, system)."""
    from hubra.core.services.mail_provisioning import (
        ensure_alias,
        resolve_local_part,
    )

    parent = db.session.get(ManagedMailAddress, parent_mma_id)
    if parent is None:
        raise ValueError(f"Parent address {parent_mma_id} not found")

    local = resolve_local_part(prefix)
    address = f"{local}@{domain}"

    existing = db.session.scalar(
        select(ManagedMailAddress).where(ManagedMailAddress.address == address)
    )
    if existing is not None:
        raise ValueError(f"Address {address} is already in use")

    alias = ManagedMailAddress(
        address=address,
        address_type="alias",
        is_protected=False,
        is_enabled=True,
        mail_prefix=local,
        kind="alias",
        local_part=local,
        domain=domain,
        owner_type="mail_address",
        owner_id=parent_mma_id,
        enabled=True,
        fixed_forward_targets=json.dumps([parent.address]),
    )
    db.session.add(alias)
    db.session.flush()
    ensure_alias(alias)
    return alias


def delete_alias(alias_id: int) -> None:
    """Deprovision and delete an alias MMA."""
    from hubra.core.services.mail_provisioning import ensure_absent

    addr = db.session.get(ManagedMailAddress, alias_id)
    if addr is None:
        return
    ensure_absent(addr)
    db.session.delete(addr)


def toggle_alias_mma(alias_id: int, enabled: bool) -> dict | None:
    addr = db.session.get(ManagedMailAddress, alias_id)
    if addr is None:
        return None
    toggle_mail_enabled(addr, enabled)
    return serialize(addr)


def list_selectable_addresses() -> list[dict]:
    """Return enabled non-system non-alias MMAs for from-whitelist dropdown."""
    addrs = list(
        db.session.scalars(
            select(ManagedMailAddress)
            .where(ManagedMailAddress.is_system.is_(False))
            .where(ManagedMailAddress.is_enabled.is_(True))
            .where(ManagedMailAddress.owner_type != "mail_address")
            .order_by(ManagedMailAddress.address)
        ).all()
    )
    return [
        {"id": a.id, "address": a.address, "ownerType": a.owner_type} for a in addrs
    ]
