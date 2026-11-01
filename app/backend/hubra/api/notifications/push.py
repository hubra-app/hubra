"""Browser push for bell notifications.

Every notification a member gets in the bell also goes to the browsers that
person turned push on in (any club: subscriptions belong to the account).
The push leaves once the notification is committed, from a Celery task, in
the person's language.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import delete, event, select

from hubra.core.extensions import db
from hubra.core.models.member import Member
from hubra.core.models.notification import Notification
from hubra.core.models.push_subscription import PushSubscription
from hubra.core.models.user import User

_log = logging.getLogger(__name__)
_MAX_PER_USER = 10  # devices one account can register


# ── Subscriptions ─────────────────────────────────────────────────────────────


def subscribe(user_id: int, endpoint: str, p256dh: str, auth: str, ua: str | None):
    """Remember this browser for *user_id* (a browser moved to another
    account is taken over). Keeps the newest ``_MAX_PER_USER``."""
    row = db.session.scalar(
        select(PushSubscription).where(PushSubscription.endpoint == endpoint)
    )
    if row is None:
        row = PushSubscription(endpoint=endpoint)
        db.session.add(row)
    row.user_id, row.p256dh, row.auth = user_id, p256dh, auth
    row.user_agent = (ua or "")[:255] or None
    row.created_at = datetime.now(timezone.utc)
    db.session.flush()
    old = db.session.scalars(
        select(PushSubscription.id)
        .where(PushSubscription.user_id == user_id)
        .order_by(PushSubscription.created_at.desc(), PushSubscription.id.desc())
        .offset(_MAX_PER_USER)
    ).all()
    if old:
        db.session.execute(delete(PushSubscription).where(PushSubscription.id.in_(old)))
    return row


def unsubscribe(user_id: int, endpoint: str) -> None:
    db.session.execute(
        delete(PushSubscription).where(
            PushSubscription.user_id == user_id, PushSubscription.endpoint == endpoint
        )
    )


def is_subscribed(user_id: int, endpoint: str) -> bool:
    return (
        db.session.scalar(
            select(PushSubscription.id).where(
                PushSubscription.user_id == user_id,
                PushSubscription.endpoint == endpoint,
            )
        )
        is not None
    )


# ── Queueing: every new notification ─────────────────────────────────────────


@event.listens_for(Notification, "after_insert")
def _queue_push(mapper, connection, target: Notification) -> None:
    """Queue the push for a new notification if its person has a device."""
    # One query: the person's account, only if it has a device.
    row = connection.execute(
        select(Member.user_id, Member.notify_prefs)
        .join(PushSubscription, PushSubscription.user_id == Member.user_id)
        .where(Member.id == target.member_id)
        .limit(1)
    ).first()
    if row is None or row.user_id is None:
        return
    from hubra.api.notifications.prefs import wants

    if not wants(row.notify_prefs, getattr(target, "topic", None), "push"):
        return
    user_id = row.user_id
    from hubra.core.tasks.after_commit import delay_after_commit
    from hubra.core.tasks.push_tasks import send_push_task
    from hubra.core.tenant.context import current_tenant

    tenant = current_tenant()
    delay_after_commit(
        send_push_task,
        user_id=user_id,
        tenant_id=tenant.id if tenant else None,
        notification_id=target.id,
        kind=target.kind,
        title=target.title,
        msg=target.msg,
        link=getattr(target, "link", None),
    )


# ── Sending ───────────────────────────────────────────────────────────────────


def club_path(slug: str | None, link: str | None) -> str:
    """Where a click on the push opens: the notification's page in its club."""
    from hubra.core.services.notification_text import safe_link

    path = safe_link(link) or "/app/dashboard"
    return f"/{slug}{path}" if slug else path


def deliver(
    user_id: int,
    tenant_id: int | None,
    notification_id: int,
    kind: str,
    title: str,
    msg: str,
    link: str | None,
) -> dict:
    """Push one notification to every device of *user_id*. Returns counts."""
    from hubra.core.models.tenant import Tenant
    from hubra.core.services import platform_settings, web_push
    from hubra.core.services.notification_text import translate

    keys = platform_settings.web_push()
    devices = db.session.scalars(
        select(PushSubscription).where(PushSubscription.user_id == user_id)
    ).all()
    summary = {"sent": 0, "removed": 0, "failed": 0}
    if keys is None or not devices:
        return summary
    user = db.session.get(User, user_id)
    tenant = db.session.get(Tenant, tenant_id) if tenant_id else None
    club = (
        ((tenant.settings or {}).get("branding") or {}).get("club_name")
        if tenant
        else None
    )
    club = club or (tenant.name if tenant else "Hubra")
    locale = (user.language if user else None) or "de-CH"
    heading, body = translate(title, msg, locale)
    message = {
        "title": heading,
        "body": body,
        "club": club,
        "url": club_path(tenant.slug if tenant else None, link),
        "tag": f"{tenant.slug if tenant else 'hubra'}-{notification_id}",
        "kind": kind,
    }
    now = datetime.now(timezone.utc)
    for device in devices:
        result = web_push.send(device, message, keys)
        if result.ok:
            device.last_used_at = now
            summary["sent"] += 1
        elif result.gone:
            db.session.delete(device)
            summary["removed"] += 1
        else:
            summary["failed"] += 1
    db.session.commit()
    return summary
