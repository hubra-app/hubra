"""What Members offers other modules through contracts (docs/contracts.md).

- ``members.badge.lookup`` (query): the club member behind a member badge
  number (``users.badge_code``, the badge on My Account and in Google
  Wallet). A check-in scans the badge and asks this club who it is.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

_CODE = re.compile(r"[^0-9A-Z]")


class BadgeRef(BaseModel):
    code: str


class BadgeMember(BaseModel):
    member_id: int


def normalise(code: str) -> str | None:
    """``hb 7k3m q9tx``, ``HB7K3MQ9TX`` or a scanned ``HB-7K3M-Q9TX`` →
    ``HB-7K3M-Q9TX``; None when it can't be a badge number."""
    raw = _CODE.sub("", (code or "").upper())
    if raw.startswith("HB") and len(raw) == 10:
        raw = raw[2:]
    if len(raw) != 8:
        return None
    return f"HB-{raw[:4]}-{raw[4:]}"


def lookup(ctx, data: BadgeRef) -> BadgeMember:
    from sqlalchemy import select

    from hubra.core.contracts import Refused
    from hubra.core.extensions import db
    from hubra.core.models.member import Member
    from hubra.core.models.user import User

    code = normalise(data.code)
    user_id = (
        db.session.scalar(select(User.id).where(User.badge_code == code))
        if code
        else None
    )
    # Several rows for one account in a club: the current membership first.
    member_id = (
        db.session.scalar(
            select(Member.id)
            .where(Member.user_id == user_id)
            .order_by(
                Member.deleted_at.is_not(None),
                Member.archived_at.is_not(None),
                Member.id,
            )
            .limit(1)
        )
        if user_id
        else None
    )
    if member_id is None:
        raise Refused(
            "No member of this club has this badge", code="NOT_FOUND", status=404
        )
    return BadgeMember(member_id=member_id)
