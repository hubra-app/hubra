"""A person's notifications from all their clubs, for the account page.

Notifications live in each club's schema, one list per member; the account
page shows them together, each tagged with its club.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import func, select

from hubra.api.notifications.services import (
    LIST_LIMIT,
    NotificationService,
    NotificationsService,
)
from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.notification import Notification
from hubra.core.models.tenant import Tenant


def _clubs(user_id: int) -> list[dict]:
    from hubra.api.auth.services import AuthService

    return [c for c in AuthService.find_user_tenants(user_id) if c.get("member_id")]


@contextmanager
def _in(club: dict) -> Iterator[None]:
    """Run in the club's schema (tests without clubs run in the default one)."""
    from hubra.core.tenant.context import in_club

    tenant = db.session.get(Tenant, club["tenant_id"]) if club["tenant_id"] else None
    if tenant is None:
        yield
        return
    with in_club(tenant):
        yield


def _club(user_id: int, slug: str | None) -> dict:
    for club in _clubs(user_id):
        if club["tenant_slug"] == slug:
            return club
    raise_error(404, "NOT_FOUND", "Club not found")
    raise AssertionError  # raise_error does not return


def list_all(user_id: int) -> dict:
    """The newest notifications of every club, newest first, and the
    number of unread ones in all of them."""
    items: list[dict] = []
    unread = 0
    for club in _clubs(user_id):
        with _in(club):
            rows = db.session.scalars(
                select(Notification)
                .where(Notification.member_id == club["member_id"])
                .order_by(Notification.time.desc(), Notification.id.desc())
                .limit(LIST_LIMIT)
            ).all()
            unread += db.session.scalar(
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.member_id == club["member_id"],
                    Notification.read.is_(False),
                )
            ) or 0
            items.extend(
                {
                    "id": n.id,
                    "kind": n.kind,
                    "title": n.title,
                    "msg": n.msg,
                    "time": n.time.isoformat(),
                    "read": n.read,
                    "link": n.link,
                    "club": {"slug": club["tenant_slug"], "name": club["tenant_name"]},
                }
                for n in rows
            )
    items.sort(key=lambda n: n["time"], reverse=True)
    return {"data": items[:LIST_LIMIT], "meta": {"unread": unread}}


def mark_read(user_id: int, slug: str | None, notification_id: int) -> None:
    club = _club(user_id, slug)
    with _in(club):
        NotificationService.mark_read(
            NotificationService.get(notification_id, club["member_id"])
        )
        db.session.commit()


def delete(user_id: int, slug: str | None, notification_id: int) -> None:
    club = _club(user_id, slug)
    with _in(club):
        NotificationService.delete(notification_id, club["member_id"])
        db.session.commit()


def mark_all_read(user_id: int) -> None:
    for club in _clubs(user_id):
        with _in(club):
            NotificationsService.mark_all_read(club["member_id"])
            db.session.commit()


def delete_all(user_id: int, read_only: bool = False) -> int:
    deleted = 0
    for club in _clubs(user_id):
        with _in(club):
            deleted += NotificationsService.delete_all(club["member_id"], read_only)
            db.session.commit()
    return deleted
