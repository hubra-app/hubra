"""Notification service — business logic for per-member in-app notifications."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, func, select

from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.member import Member
from hubra.core.models.notification import Notification

_MAX_TEXT = 255  # title and msg columns
LIST_LIMIT = 100  # newest notifications the bell gets


def _fit(text: str) -> str:
    """Shorten text to the column size; a prefixed title ("New vote: …")
    can exceed it even when the poll question fits."""
    return text if len(text) <= _MAX_TEXT else text[: _MAX_TEXT - 1] + "…"


def notify_all_active(
    kind: str,
    title: str,
    msg: str,
    skip_member_id: int | None = None,
    link: str | None = None,
) -> None:
    """Create a notification for every active (non-archived) member."""
    members = db.session.scalars(
        select(Member.id)
        .where(Member.status == "active")
        .where(Member.archived_at.is_(None))
    ).all()
    for member_id in members:
        if skip_member_id is not None and member_id == skip_member_id:
            continue
        db.session.add(
            Notification(
                member_id=member_id,
                kind=kind,
                title=_fit(title),
                msg=_fit(msg),
                link=link,
            )
        )


def notify_on_publish(
    module_code: str,
    kind: str,
    title: str,
    msg: str,
    skip_member_id: int | None = None,
    link: str | None = None,
) -> None:
    """``notify_all_active`` unless the club switched the module's
    "notify members" setting off (posts, events, polls)."""
    from hubra.core.modules import get_config

    if get_config(module_code).get("notify_members", True) is False:
        return
    notify_all_active(kind, title, msg, skip_member_id=skip_member_id, link=link)


def notify_member(
    member_id: int, kind: str, title: str, msg: str, link: str | None = None
) -> None:
    """Create a notification for a single member."""
    db.session.add(
        Notification(
            member_id=member_id, kind=kind, title=_fit(title), msg=_fit(msg), link=link
        )
    )


def create_notification(
    member_id: int,
    kind: str = "info",
    title: str = "",
    msg: str = "",
    link: str | None = None,
) -> Notification:
    """Create, flush and return an unread notification for one member."""
    notif = Notification(
        member_id=member_id,
        kind=kind,
        title=_fit(title),
        msg=_fit(msg),
        time=datetime.now(timezone.utc),
        read=False,
        link=link,
    )
    db.session.add(notif)
    db.session.flush()
    return notif


class NotificationService:
    """Operations on a single notification."""

    @staticmethod
    def get(notification_id: int, member_id: int) -> Notification:
        """Return a notification scoped to member, or raise 404."""
        notification = db.session.scalar(
            select(Notification)
            .where(Notification.id == notification_id)
            .where(Notification.member_id == member_id)
        )
        if notification is None:
            raise_error(404, "NOT_FOUND", f"Notification {notification_id} not found")
        return notification  # type: ignore[return-value]

    @staticmethod
    def mark_read(notification: Notification) -> Notification:
        """Mark a notification as read."""
        notification.read = True
        return notification

    @staticmethod
    def delete(notification_id: int, member_id: int) -> None:
        """Delete a notification scoped to member."""
        notification = db.session.scalar(
            select(Notification)
            .where(Notification.id == notification_id)
            .where(Notification.member_id == member_id)
        )
        if notification is None:
            raise_error(404, "NOT_FOUND", f"Notification {notification_id} not found")
        db.session.delete(notification)


class NotificationsService:
    """Operations on the notification collection."""

    @staticmethod
    def list(member_id: int) -> dict:
        """Return a member's newest notifications with the unread count.

        Nothing deletes old notifications, so the list is capped; the
        unread count still covers all of them."""
        notifications = db.session.scalars(
            select(Notification)
            .where(Notification.member_id == member_id)
            .order_by(Notification.time.desc(), Notification.id.desc())
            .limit(LIST_LIMIT)
        ).all()

        unread = db.session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.member_id == member_id, Notification.read.is_(False))
        )
        return {
            "data": notifications,
            "meta": {"unread": unread},
        }

    @staticmethod
    def mark_all_read(member_id: int) -> None:
        """Mark all unread notifications as read for a member."""
        unread = db.session.scalars(
            select(Notification)
            .where(Notification.member_id == member_id)
            .where(Notification.read.is_(False))
        ).all()

        for n in unread:
            n.read = True

    @staticmethod
    def delete_all(member_id: int, read_only: bool = False) -> int:
        """Delete a member's notifications (only the read ones with
        ``read_only``) and return how many went."""
        query = delete(Notification).where(Notification.member_id == member_id)
        if read_only:
            query = query.where(Notification.read.is_(True))
        return db.session.execute(query).rowcount or 0
