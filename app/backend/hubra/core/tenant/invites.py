"""Invite someone to a club by email, and accept the invite.

A club never creates or changes an account: it sends a personal link
(``<SSO>/invite#token=…``). The person signs in with the invited address, or
signs up with it, and accepts on the SSO portal, which makes them a member.
Nothing of their account reaches the club before they accept.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from hubra.core.extensions import db
from hubra.core.models.club_invite import ClubInvite
from hubra.core.models.tenant import Tenant
from hubra.core.models.user import User
from hubra.core.tenant.club_settings import club_setting

INVITE_DAYS = 14
# Invites go to any address from the platform's sender: a club gets this many
# a day, plenty for importing its member list, too few to spam with.
INVITES_PER_DAY = 500

# Member fields a club can decide before the person accepts.
MEMBER_DATA_FIELDS = ("tier_id", "group_ids", "status", "membership_type", "notes")


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def send_invite(
    tenant: Tenant,
    email: str,
    invited_by: str,
    *,
    name: str = "",
    member_data: dict | None = None,
) -> ClubInvite:
    """Email ``email`` a fresh invite to ``tenant`` (older open ones stop working)."""
    from hubra.core.services import email as email_svc

    from hubra.core.errors import raise_error

    email = email.strip().lower()
    since = datetime.now(timezone.utc) - timedelta(days=1)
    sent_today = db.session.scalar(
        select(func.count(ClubInvite.id)).where(
            ClubInvite.tenant_id == tenant.id, ClubInvite.created_at >= since
        )
    )
    if (sent_today or 0) >= INVITES_PER_DAY:
        raise_error(
            429, "TOO_MANY_INVITES", "This club has sent its invites for today"
        )
    db.session.execute(
        delete(ClubInvite).where(
            ClubInvite.tenant_id == tenant.id,
            ClubInvite.email == email,
            ClubInvite.accepted_at.is_(None),
        )
    )
    raw = secrets.token_urlsafe(32)
    data = {k: v for k, v in (member_data or {}).items() if k in MEMBER_DATA_FIELDS}
    invite = ClubInvite(
        tenant_id=tenant.id,
        email=email,
        token_hash=_hash(raw),
        invited_by=(invited_by or "")[:255],
        member_data=data or None,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=club_setting(tenant, "invite_valid_days", INVITE_DAYS)),
    )
    db.session.add(invite)
    db.session.flush()

    user = db.session.scalar(select(User).where(User.email == email))
    invite_url = f"{email_svc._get_sso_base_url()}/invite#token={raw}"
    email_svc.send_club_invite(
        email,
        (user.name if user else name) or email,
        invite_url,
        invited_by,
        lang=(user.language if user else None) or "de-CH",
    )
    return invite


def open_invite(raw: str) -> ClubInvite | None:
    """The invite behind a link, while it can still be accepted."""
    if not raw:
        return None
    invite = db.session.scalar(
        select(ClubInvite).where(ClubInvite.token_hash == _hash(raw))
    )
    if invite is None or not invite.is_open:
        return None
    return invite
