"""Polling-based WildDuck message count sync.

Replaces the abandoned ``storage.new`` webhook approach — WildDuck has no
such event (confirmed against lib/events.js which only exposes dkim.*,
cert.*, domainalias.*, address.*, filter.*, asp.*, user.*, autoreply.*,
mfa.*, mailbox.*, marked.spam, marked.ham, "forward added").

Counts are tracked per-mailbox-folder to support multiple IMAP folders
(INBOX, Sent, …) for each member.  Business logic is delegated to
MailboxService; this task only orchestrates the batch loop.
"""

from __future__ import annotations

import logging

from vollbuild.core.modules import per_tenant_job
from vollbuild.core.tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=0, acks_late=True, reject_on_worker_lost=True)
def sync_wildduck_message_counts(self) -> dict:
    """Sync message/unread counts from WildDuck into MailboxFolder rows.

    Queries all member ManagedMailAddress entries with an active
    ``wildduck_user_id``, fetches their WildDuck mailbox list with
    counters, and upserts a MailboxFolder row for every folder returned.
    Fails for individual members are logged but do not abort the batch.
    """
    return _sync_wildduck_message_counts()


@per_tenant_job("mail")
def _sync_wildduck_message_counts() -> dict:
    from sqlalchemy import select

    from vollbuild.api.mail.services import MailboxService
    from vollbuild.core.extensions import db
    from vollbuild.core.models.managed_mail import ManagedMailAddress
    from vollbuild.core.services.wildduck import WildDuckError, try_get_client

    wd = try_get_client()
    if wd is None:
        logger.debug("sync_wildduck_message_counts: WildDuck not configured, skipping")
        return {"ok": False, "reason": "WildDuck not configured"}

    addrs = db.session.scalars(
        select(ManagedMailAddress)
        .where(ManagedMailAddress.owner_type == "member")
        .where(ManagedMailAddress.wildduck_user_id.isnot(None))
    ).all()

    total_members = len(addrs)
    updated_members = 0
    skipped_members = 0
    total_folders = 0

    for addr in addrs:
        _total, _unseen, mailboxes = MailboxService.get_mailbox_totals(
            addr.wildduck_user_id,  # type: ignore[arg-type]
            wd,
        )

        if not mailboxes:
            skipped_members += 1
            continue

        try:
            MailboxService.upsert_folders(addr.owner_id, mailboxes)  # type: ignore[arg-type]
            total_folders += len(mailboxes)
            updated_members += 1
        except (WildDuckError, KeyError) as exc:
            logger.warning(
                "sync_wildduck_message_counts: error for member %s: %s",
                addr.owner_id,
                exc,
            )
            skipped_members += 1

    db.session.commit()

    logger.info(
        "sync_wildduck_message_counts: %d members processed, "
        "%d folders updated, %d members skipped",
        total_members,
        total_folders,
        skipped_members,
    )

    return {
        "ok": True,
        "total_members": total_members,
        "updated_folders": total_folders,
        "skipped_members": skipped_members,
    }


@celery_app.task(bind=True, max_retries=0, acks_late=True, reject_on_worker_lost=True)
def sync_wildduck_quota(self) -> dict:
    """Sync quota (used + allowed) from WildDuck into ManagedMailAddress rows.

    Calls ``wd.list_users(limit=250)`` once and batch-updates ``quota_used``
    and ``quota_bytes`` on every matching ManagedMailAddress.  This keeps the
    mail list endpoints DB-only — they no longer call WildDuck synchronously.

    Runs every 5 minutes via Celery beat.
    """
    return _sync_wildduck_quota()


@per_tenant_job("mail")
def _sync_wildduck_quota() -> dict:
    from datetime import datetime, timezone

    from sqlalchemy import select

    from vollbuild.core.extensions import db
    from vollbuild.core.models.managed_mail import ManagedMailAddress
    from vollbuild.core.services.wildduck import WildDuckError, try_get_client

    wd = try_get_client()
    if wd is None:
        logger.debug("sync_wildduck_quota: WildDuck not configured, skipping")
        return {"ok": False, "reason": "WildDuck not configured"}

    try:
        result = wd.list_users(limit=250)
    except WildDuckError as exc:
        logger.warning("sync_wildduck_quota: WildDuck error: %s", exc)
        return {"ok": False, "reason": str(exc)}

    wd_quota: dict[str, dict] = {}
    for u in result.get("results", []):
        uid = u.get("id")
        if uid:
            quota = u.get("quota") or {}
            wd_quota[uid] = {
                "used": quota.get("used", 0),
                "allowed": quota.get("allowed", 0),
            }

    addrs = db.session.scalars(
        select(ManagedMailAddress)
        .where(ManagedMailAddress.address_type == "mailbox")
        .where(
            ManagedMailAddress.wildduck_id.isnot(None)
            | ManagedMailAddress.wildduck_user_id.isnot(None)
        )
    ).all()

    updated = 0
    now = datetime.now(timezone.utc)
    for addr in addrs:
        wd_id = addr.wildduck_id or addr.wildduck_user_id
        if not wd_id:
            continue
        qd = wd_quota.get(wd_id)
        if qd is None:
            continue
        addr.quota_used = qd["used"]
        if qd["allowed"]:
            addr.quota_bytes = qd["allowed"]
        addr.last_synced_at = now
        updated += 1

    db.session.commit()
    logger.info("sync_wildduck_quota: %d of %d addresses updated", updated, len(addrs))
    return {"ok": True, "updated": updated, "total": len(addrs)}
