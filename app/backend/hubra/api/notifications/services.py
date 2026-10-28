"""Notification service — business logic for per-member in-app notifications."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.member import Member
from hubra.core.models.notification import Notification


def notify_all_active(
    kind: str, title: str, msg: str, skip_member_id: int | None = None
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
            Notification(member_id=member_id, kind=kind, title=title, msg=msg)
        )


def notify_on_publish(
    module_code: str,
    kind: str,
    title: str,
    msg: str,
    skip_member_id: int | None = None,
) -> None:
    """``notify_all_active`` unless the club switched the module's
    "notify members" setting off (posts, events, polls)."""
    from hubra.core.modules import get_config

    if get_config(module_code).get("notify_members", True) is False:
        return
    notify_all_active(kind, title, msg, skip_member_id=skip_member_id)


def notify_member(member_id: int, kind: str, title: str, msg: str) -> None:
    """Create a notification for a single member."""
    db.session.add(Notification(member_id=member_id, kind=kind, title=title, msg=msg))


def create_notification(
    member_id: int, kind: str = "info", title: str = "", msg: str = ""
) -> Notification:
    """Create, flush and return an unread notification for one member."""
    notif = Notification(
        member_id=member_id,
        kind=kind,
        title=title,
        msg=msg,
        time=datetime.now(timezone.utc),
        read=False,
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
        """Return notifications for a member with unread count."""
        notifications = db.session.scalars(
            select(Notification)
            .where(Notification.member_id == member_id)
            .order_by(Notification.time.desc())
        ).all()

        unread = sum(1 for n in notifications if not n.read)
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
