"""Notify the members who can act on something (an application, a request
to leave) instead of everyone."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from hubra.api.notifications.services import notify_member
from hubra.core.extensions import db
from hubra.core.models.member import Member


def notify_permitted(
    perm_key: str,
    kind: str,
    title: str,
    msg: str,
    skip_member_id: int | None = None,
    link: str | None = None,
) -> None:
    """Notify every active member who is an admin or holds ``perm_key``
    (e.g. ``"applications.applications.approve"``)."""
    from hubra.api.permissions import _get_member_permission_keys, member_is_admin

    members = db.session.scalars(
        select(Member)
        .where(Member.archived_at.is_(None))
        .options(selectinload(Member.roles), selectinload(Member.user))
    ).all()
    for member in members:
        if member.id == skip_member_id or member.is_blocked:
            continue
        if member_is_admin(member) or perm_key in _get_member_permission_keys(member):
            notify_member(member.id, kind, title, msg, link=link)
