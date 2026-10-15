"""Periodic Celery tasks — retention cleanup and mail reconciliation."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from vollbuild.core.tasks import celery_app

logger = logging.getLogger(__name__)

_DEFAULT_RETENTION_DAYS = 365


@celery_app.task(bind=True, max_retries=0, acks_late=True, reject_on_worker_lost=True)
def retention_cleanup(self) -> dict:
    """Delete messages older than each member's retention window.

    Runs daily (wired by Celery Beat at 02:00 UTC). Iterates all members
    with an active WildDuck mailbox, determines per-member retention in days,
    fetches all IMAP folders via list_mailboxes, then pages through every
    folder and deletes messages that exceed the cutoff.

    Falls back to _DEFAULT_RETENTION_DAYS (365) when neither member.retention_days
    nor the mail.retention_default_days system setting is configured.

    Returns a summary dict: {processed, deleted, errors}.
    """
    from vollbuild.api.features.services import FeatureFlagService

    if not FeatureFlagService.is_enabled_sync("mail"):
        logger.debug("retention_cleanup: mail feature disabled, skipping")
        return {"skipped": "mail disabled"}

    from sqlalchemy import select

    from vollbuild.api.settings.services import SettingService
    from vollbuild.core.extensions import db
    from vollbuild.core.models.managed_mail import ManagedMailAddress
    from vollbuild.core.models.member import Member
    from vollbuild.core.services.wildduck import WildDuckError, try_get_client

    wd = try_get_client()
    if wd is None:
        logger.debug("retention_cleanup: WildDuck not configured, skipping")
        return {"processed": 0, "deleted": 0, "errors": 0}

    # Get member MMAs with active WildDuck users (check both legacy and new ID columns)
    addrs = db.session.scalars(
        select(ManagedMailAddress)
        .where(ManagedMailAddress.owner_type == "member")
        .where(
            (ManagedMailAddress.wildduck_user_id.isnot(None))
            | (ManagedMailAddress.wildduck_id.isnot(None))
        )
    ).all()

    processed = 0
    deleted = 0
    errors = 0

    for addr in addrs:
        member = db.session.get(Member, addr.owner_id)
        if member is None:
            continue
        # Determine retention window (ms): MMA row first, then member, then global
        if addr.retention is not None and addr.retention > 0:
            retention_ms = addr.retention
        elif member.retention_days is not None:
            retention_ms = member.retention_days * 86400000
        else:
            # Member default: retention OFF (None on MMA). Skip unless global
            # default is explicitly configured.
            if addr.kind == "member" and addr.retention is None:
                continue
            default_setting = SettingService.get("mail.retention_default_days")
            if default_setting is not None:
                try:
                    retention_ms = int(default_setting.value) * 86400000
                except (TypeError, ValueError):
                    retention_ms = _DEFAULT_RETENTION_DAYS * 86400000
            else:
                retention_ms = _DEFAULT_RETENTION_DAYS * 86400000

        # Use unified wildduck_id (with legacy fallback)
        wd_user_id = addr.wildduck_id or addr.wildduck_user_id

        cutoff_ms = int(
            (
                datetime.now(timezone.utc) - timedelta(milliseconds=retention_ms)
            ).timestamp()
            * 1000
        )
        cutoff_date = (
            datetime.fromtimestamp(cutoff_ms / 1000, tz=timezone.utc).date().isoformat()
        )

        member_deleted = 0
        try:
            # Fetch all IMAP folders so retention applies across INBOX, Sent, etc.
            folders_resp = wd.list_mailboxes(wd_user_id)  # type: ignore[arg-type]
            folders = folders_resp.get("results", [])

            for folder in folders:
                folder_id = folder.get("id")
                if not folder_id:
                    continue

                page = 1
                while True:
                    result = wd.list_user_messages(
                        wd_user_id,  # type: ignore[arg-type]
                        mailbox=folder_id,
                        limit=250,
                        page=page,  # type: ignore[arg-type]
                    )
                    messages = result.get("results", [])
                    if not messages:
                        break

                    for msg in messages:
                        msg_date = msg.get("date", 0)
                        if isinstance(msg_date, (int, float)) and msg_date < cutoff_ms:
                            wd.delete_user_message(
                                wd_user_id,  # type: ignore[arg-type]
                                folder_id,
                                str(msg["id"]),  # type: ignore[arg-type]
                            )
                            member_deleted += 1

                    total = result.get("total", 0)
                    if len(messages) < 250 or page * 250 >= total:
                        break
                    page += 1

            logger.info(
                "retention_cleanup: deleted %d messages for member %d (cutoff %s)",
                member_deleted,
                member.id,
                cutoff_date,
            )
            deleted += member_deleted
            processed += 1

        except WildDuckError as exc:
            logger.warning(
                "retention_cleanup: WildDuck error for member %d: %s", member.id, exc
            )
            errors += 1

    return {"processed": processed, "deleted": deleted, "errors": errors}


@celery_app.task(bind=True, max_retries=0, acks_late=True, reject_on_worker_lost=True)
def cleanup_token_blocklist(self) -> dict:
    """Delete expired JWT tokens from the blocklist.

    Runs daily (Celery Beat at 03:00 UTC). Tokens older than 30 days are safe
    to remove — no valid JWT can have a lifetime that long.

    Returns a summary dict: {deleted}.
    """
    from sqlalchemy import delete

    from vollbuild.core.extensions import db
    from vollbuild.core.models.token import TokenBlocklist

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    result = db.session.execute(
        delete(TokenBlocklist).where(TokenBlocklist.created_at < cutoff)
    )
    db.session.commit()
    deleted = result.rowcount  # type: ignore[attr-defined]
    logger.info("cleanup_token_blocklist: deleted %d expired tokens", deleted)
    return {"deleted": deleted}


@celery_app.task(bind=True, max_retries=0, acks_late=True, reject_on_worker_lost=True)
def verify_protected_mail_addresses(self) -> dict:
    """Verify that protected ManagedMailAddress rows are still provisioned in WildDuck.

    Runs daily (Celery Beat at 04:00 UTC).  For each protected MMA:
    - alias type: checks wildduck_id via get_address(); on 404 clears
      the ID and dispatches sync_managed_address.
    - mailbox type: checks wildduck_user_id via get_user(); on 404 clears
      IDs and dispatches provision_member_mail.

    Returns a summary dict: {verified, re_provisioned, errors}.
    """
    from vollbuild.api.features.services import FeatureFlagService

    if not FeatureFlagService.is_enabled_sync("mail"):
        logger.debug("verify_protected_mail_addresses: mail feature disabled, skipping")
        return {"skipped": "mail disabled"}

    from sqlalchemy import select

    from vollbuild.api.utils import log_audit
    from vollbuild.core.extensions import db
    from vollbuild.core.models.managed_mail import ManagedMailAddress
    from vollbuild.core.services.wildduck import WildDuckError, try_get_client
    from vollbuild.core.tasks.wildduck import (
        provision_member_mail,
        sync_managed_address,
    )

    wd = try_get_client()
    if wd is None:
        logger.debug(
            "verify_protected_mail_addresses: WildDuck not configured, skipping"
        )
        return {"verified": 0, "re_provisioned": 0, "errors": 0}

    protected_addrs = db.session.scalars(
        select(ManagedMailAddress).where(ManagedMailAddress.is_protected.is_(True))
    ).all()

    verified = 0
    re_provisioned = 0
    errors = 0

    try:
        for addr in protected_addrs:
            if addr.address_type == "alias" and addr.wildduck_id:
                try:
                    wd.get_address(addr.wildduck_id)
                    verified += 1
                except WildDuckError as exc:
                    if exc.status != 404:
                        errors += 1
                        continue
                    logger.warning(
                        "verify_protected: alias %s not found in WildDuck for %s — re-provisioning",
                        addr.wildduck_id,
                        addr.address,
                    )
                    addr.wildduck_id = None
                    addr.provisioning_status = "pending"
                    sync_managed_address.delay(addr.id)
                    log_audit(
                        actor_id=None,
                        action="mail_stale_id_detected",
                        target_type="ManagedMailAddress",
                        target_id=addr.id,
                        target_label=addr.address,
                    )
                    re_provisioned += 1

            elif addr.address_type == "mailbox" and addr.wildduck_user_id:
                try:
                    wd.get_user(addr.wildduck_user_id)
                    verified += 1
                except WildDuckError as exc:
                    if exc.status != 404:
                        errors += 1
                        continue
                    logger.warning(
                        "verify_protected: user %s not found in WildDuck for %s — re-provisioning",
                        addr.wildduck_user_id,
                        addr.address,
                    )
                    addr.wildduck_user_id = None
                    addr.wildduck_filter_id = None
                    addr.provisioning_status = "pending"
                    if addr.owner_type == "member":
                        provision_member_mail.delay(addr.owner_id)
                    log_audit(
                        actor_id=None,
                        action="mail_stale_id_detected",
                        target_type="ManagedMailAddress",
                        target_id=addr.id,
                        target_label=addr.address,
                    )
                    re_provisioned += 1

    except Exception:
        logger.warning(
            "verify_protected: error checking %s", addr.address, exc_info=True
        )
        errors += 1

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    logger.info(
        "verify_protected_mail_addresses: verified=%d, re_provisioned=%d, errors=%d",
        verified,
        re_provisioned,
        errors,
    )
    return {"verified": verified, "re_provisioned": re_provisioned, "errors": errors}


# ── New-generation reconciliation & quota check ──────────────────────────


@celery_app.task(bind=True, max_retries=0, acks_late=True, reject_on_worker_lost=True)
def reconcile_mail(self) -> dict:
    """Reconcile all ManagedMailAddress rows against WildDuck.

    Walks every row, compares desired state against WildDuck, and
    overwrites WildDuck to match the backend (backend-always-wins).

    Also performs an orphan sweep: finds WildDuck user/alias IDs that
    have no backing ``ManagedMailAddress`` row and removes them.

    New-generation version using ``MailProvisioningService`` primitives.
    Runs every 15 minutes.
    """
    from vollbuild.api.features.services import FeatureFlagService

    if not FeatureFlagService.is_enabled_sync("mail"):
        logger.debug("reconcile_mail: mail feature disabled, skipping")
        return {"skipped": "mail disabled"}

    from sqlalchemy import select

    from vollbuild.core.extensions import db
    from vollbuild.core.models.managed_mail import ManagedMailAddress
    from vollbuild.core.services.mail_provisioning import (
        _resolve_function_holder_targets,
        _resolve_group_member_targets,
        _resolve_member_forward_targets,
        _resolve_system_forward_targets,
        ensure_absent,
        ensure_alias,
        ensure_catchall,
        ensure_forwarding,
        ensure_mailbox,
    )
    from vollbuild.core.services.wildduck import WildDuckError, try_get_client

    wd = try_get_client()

    # ── Step 0: Auto-create missing MMAs for groups, functions, members ────
    created = _create_missing_mmas()

    # ── Step 0.5: Remove orphaned MMAs (owner deleted) ─────────────────────
    from vollbuild.core.models.function import Function
    from vollbuild.core.models.group import Group
    from vollbuild.core.models.member import Member

    addrs = list(
        db.session.scalars(
            select(ManagedMailAddress).order_by(ManagedMailAddress.id)
        ).all()
    )

    removed = 0

    for mma in addrs:
        if mma.owner_type == "group" and mma.owner_id:
            if db.session.get(Group, mma.owner_id) is None:
                ensure_absent(mma)
                db.session.delete(mma)
                removed += 1
        elif mma.owner_type == "function" and mma.owner_id:
            if db.session.get(Function, mma.owner_id) is None:
                ensure_absent(mma)
                db.session.delete(mma)
                removed += 1
        elif mma.owner_type == "member" and mma.owner_id:
            member_row = db.session.get(Member, mma.owner_id)
            if member_row is None:
                ensure_absent(mma)
                db.session.delete(mma)
                removed += 1

    # Refresh addr list after auto-create and orphan removal
    addrs = list(
        db.session.scalars(
            select(ManagedMailAddress).order_by(ManagedMailAddress.id)
        ).all()
    )

    provisioned = 0
    errors = 0

    for mma in addrs:
        try:
            if mma.local_part == "*":
                ensure_catchall(mma)
            elif mma.kind == "group":
                if mma.enabled is False:
                    ensure_absent(mma)
                elif mma.address_type == "mailbox":
                    ensure_mailbox(mma)
                    ensure_alias(mma)
                    targets = _resolve_group_member_targets(mma.owner_id or 0)
                    ensure_forwarding(mma, targets)
                else:
                    ensure_alias(mma)
            elif mma.kind == "function":
                if mma.enabled is False:
                    ensure_absent(mma)
                elif mma.address_type == "mailbox":
                    ensure_mailbox(mma)
                    ensure_alias(mma)
                    targets = _resolve_function_holder_targets(mma.owner_id or 0)
                    ensure_forwarding(mma, targets)
                else:
                    ensure_alias(mma)
            elif mma.kind == "member":
                if mma.enabled is False:
                    continue
                elif mma.address_type == "mailbox":
                    from vollbuild.core.models.member import Member

                    member = db.session.get(Member, mma.owner_id)  # type: ignore[assignment]
                    if member and not member.archived_at and not member.is_disabled:
                        ensure_mailbox(mma, password_hash=member.password_hash)
                        ensure_alias(mma)
                        targets = _resolve_member_forward_targets(mma)
                        ensure_forwarding(mma, targets)
                    elif member and (member.archived_at or member.is_disabled):
                        if mma.wildduck_id and wd is not None:
                            try:
                                wd.update_user_attributes(
                                    mma.wildduck_id, disabled=True
                                )
                            except WildDuckError:
                                logger.warning(
                                    "reconcile_mail: failed to disable user for member MMA %d",
                                    mma.id,
                                )
            elif mma.address_type == "mailbox":
                ensure_mailbox(mma)
                if mma.kind == "system":
                    targets = _resolve_system_forward_targets(mma)
                    ensure_forwarding(mma, targets)
            elif mma.address_type != "mailbox":
                ensure_alias(mma)
            provisioned += 1
        except WildDuckError:
            errors += 1
            logger.warning(
                "reconcile_mail: error provisioning MMA %d (%s)", mma.id, mma.address
            )

    # ── Step 1.5: Re-sync fromWhitelist for all mailbox MMAs ──────────────
    from vollbuild.core.services.mail_provisioning import sync_from_whitelist_for_mma

    for mma in addrs:
        if (
            mma.address_type == "mailbox"
            and mma.wildduck_id
            and mma.enabled is not False
        ):
            try:
                sync_from_whitelist_for_mma(mma)
            except Exception:
                logger.debug(
                    "reconcile_mail: fromWhitelist sync failed for MMA %d", mma.id
                )

    # ── Step 2: Orphan sweep (only when WildDuck is reachable) ─────────────
    orphans_removed = 0
    if wd is not None:
        known_user_ids = {
            a.wildduck_id
            for a in addrs
            if a.wildduck_id and a.address_type == "mailbox"
        }
        # Walk WildDuck users and remove unmanaged ones
        try:
            page = 1
            while True:
                users_resp = wd.list_users(limit=250, page=page)
                users = users_resp.get("results", [])
                if not users:
                    break
                for user in users:
                    uid = user.get("id")
                    if uid and uid not in known_user_ids:
                        is_managed = bool(
                            db.session.scalar(
                                select(ManagedMailAddress.id).where(
                                    ManagedMailAddress.wildduck_id == uid
                                )
                            )
                        )
                        if not is_managed:
                            wd.safe_delete_user(uid)
                            orphans_removed += 1
                            logger.info("reconcile_mail: removed orphan user %s", uid)
                page += 1
                if len(users) < 250:
                    break
        except WildDuckError:
            logger.warning("reconcile_mail: orphan sweep failed (WildDuck error)")

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    logger.info(
        "reconcile_mail: created=%d, removed=%d, provisioned=%d, errors=%d, orphans_removed=%d",
        created,
        removed,
        provisioned,
        errors,
        orphans_removed,
    )
    return {
        "created": created,
        "removed": removed,
        "provisioned": provisioned,
        "errors": errors,
        "orphans_removed": orphans_removed,
    }


@celery_app.task(bind=True, max_retries=0, acks_late=True, reject_on_worker_lost=True)
def reconcile_entity_forwarding_task(self, entity_type: str, entity_id: int) -> None:
    """Celery wrapper for reconcile_entity_forwarding.

    Dispatched by membership-change hooks (group member add/remove,
    function holder assign/remove, member archive, set_groups).
    """
    from vollbuild.api.features.services import FeatureFlagService

    if not FeatureFlagService.is_enabled_sync("mail"):
        logger.debug(
            "reconcile_entity_forwarding_task: mail feature disabled, skipping"
        )
        return

    from vollbuild.core.extensions import db
    from vollbuild.core.services.mail_provisioning import reconcile_entity_forwarding

    try:
        reconcile_entity_forwarding(entity_type, entity_id)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.warning(
            "reconcile_entity_forwarding_task: error for %s %d",
            entity_type,
            entity_id,
            exc_info=True,
        )
        raise


@celery_app.task(bind=True, max_retries=0, acks_late=True, reject_on_worker_lost=True)
def check_mailbox_quota(self) -> dict:
    """Check all mailbox-backed MMAs for near-full mailboxes.

    Flags any mailbox at/above 90% (``quota.used / quota.allowed``) and
    sends a localized alert to the mailbox owner + postmaster.

    Respects a 24-hour cooldown via ``last_quota_alert_at``.
    Runs hourly.
    """
    from vollbuild.api.features.services import FeatureFlagService

    if not FeatureFlagService.is_enabled_sync("mail"):
        logger.debug("check_mailbox_quota: mail feature disabled, skipping")
        return {"skipped": "mail disabled"}

    from datetime import timedelta

    from sqlalchemy import select

    from vollbuild.api.utils import log_audit
    from vollbuild.core.extensions import db
    from vollbuild.core.models.managed_mail import ManagedMailAddress
    from vollbuild.core.models.member import Member
    from vollbuild.core.services.wildduck import WildDuckError, try_get_client
    from vollbuild.core.tasks.wildduck import _get_club_domain_safe
    from vollbuild.core.services.email import _send as send_email

    wd = try_get_client()
    if wd is None:
        logger.debug("check_mailbox_quota: WildDuck not configured, skipping")
        return {"checked": 0, "alerts_sent": 0, "errors": 0}

    cooldown = timedelta(hours=24)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    ninety_pct = 0.9

    addrs = list(
        db.session.scalars(
            select(ManagedMailAddress)
            .where(ManagedMailAddress.address_type == "mailbox")
            .where(ManagedMailAddress.wildduck_id.isnot(None))
        ).all()
    )

    checked = 0
    alerts_sent = 0
    errors = 0

    for mma in addrs:
        try:
            quota = wd.get_user_quota(mma.wildduck_id)  # type: ignore[arg-type]
            allowed = quota.get("allowed", 0)
            used = quota.get("used", 0)
            if allowed <= 0:
                continue
            if used / allowed < ninety_pct:
                continue

            # Cooldown check
            if mma.last_quota_alert_at and (now - mma.last_quota_alert_at) < cooldown:
                continue

            # Determine recipient(s)
            owner_emails: list[str] = []
            if mma.owner_type == "member" and mma.owner_id:
                member = db.session.get(Member, mma.owner_id)
                if member and member.email:
                    owner_emails.append(member.email)

            postmaster_address = f"postmaster@{_get_club_domain_safe()}"
            all_recipients = list(set(owner_emails + [postmaster_address]))

            pct = int(used / allowed * 100)
            subject = f"Mailbox {mma.address} is {pct}% full"
            body = (
                f"The mailbox {mma.address} has reached {pct}% of its quota "
                f"({used // (1024 * 1024)} MB used of {allowed // (1024 * 1024)} MB)."
            )

            for email_addr in all_recipients:
                try:
                    send_email(
                        to_email=email_addr,
                        to_name=email_addr.split("@")[0],
                        subject=subject,
                        body_html=f"<p>{body}</p>",
                        body_text=body,
                    )
                except Exception:
                    logger.warning(
                        "check_mailbox_quota: failed to send alert to %s", email_addr
                    )

            mma.last_quota_alert_at = now
            alerts_sent += 1
            checked += 1

            log_audit(
                actor_id=None,
                action="mailbox_quota_alert",
                target_type="ManagedMailAddress",
                target_id=mma.id,
                target_label=f"{mma.address} at {pct}%",
            )

        except WildDuckError as exc:
            errors += 1
            logger.warning(
                "check_mailbox_quota: WildDuck error for MMA %d: %s", mma.id, exc
            )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    logger.info(
        "check_mailbox_quota: checked=%d, alerts_sent=%d, errors=%d",
        checked,
        alerts_sent,
        errors,
    )
    return {"checked": checked, "alerts_sent": alerts_sent, "errors": errors}


def _create_missing_mmas() -> int:
    """Create a ManagedMailAddress for every group, function and active
    member that has none. Returns how many were created."""
    from sqlalchemy import select

    from vollbuild.core.extensions import db
    from vollbuild.core.models.function import Function
    from vollbuild.core.models.group import Group
    from vollbuild.core.models.managed_mail import ManagedMailAddress
    from vollbuild.core.models.member import Member
    from vollbuild.core.services.managed_mail import (
        auto_create_mma_for_function,
        auto_create_mma_for_group,
        auto_create_mma_for_member,
    )

    existing = set(
        db.session.execute(
            select(ManagedMailAddress.owner_type, ManagedMailAddress.owner_id)
        ).all()
    )
    owners = [
        ("group", select(Group.id), auto_create_mma_for_group),
        ("function", select(Function.id), auto_create_mma_for_function),
        (
            "member",
            select(Member.id).where(Member.archived_at.is_(None)),
            auto_create_mma_for_member,
        ),
    ]
    created = 0
    for owner_type, ids_query, create in owners:
        for owner_id in db.session.scalars(ids_query).all():
            if (owner_type, owner_id) not in existing:
                create(owner_id)
                created += 1
    return created
