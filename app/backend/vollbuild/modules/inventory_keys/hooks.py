"""Event handlers for the keys module."""

from __future__ import annotations

from sqlalchemy import select

from vollbuild.core.extensions import db
from vollbuild.core.models.member import Member

from .models import Key


def on_invoice_overdue(tenant_id, member_id: int, invoice_id: int, **_):
    """Tell the key managers when someone with an overdue invoice holds keys.

    A physical key cannot be switched off like an RFID tag, so the club
    decides whether to ask for it back.
    """
    from vollbuild.api.notifications.services import create_notification
    from vollbuild.api.permissions import _get_member_permission_keys, member_is_admin

    keys = db.session.scalars(
        select(Key).where(Key.holder_id == member_id, Key.status == "issued")
    ).all()
    if not keys:
        return
    member = db.session.get(Member, member_id)
    labels = ", ".join(k.label for k in keys)
    managers = [
        m
        for m in db.session.scalars(
            select(Member).where(Member.archived_at.is_(None))
        ).all()
        if member_is_admin(m) or "keys.keys.manage" in _get_member_permission_keys(m)
    ]
    for manager in managers:
        create_notification(
            manager.id,
            kind="warning",
            title="Overdue invoice, keys issued",
            msg=f"{member.name if member else member_id} holds {labels}"[:255],
        )
