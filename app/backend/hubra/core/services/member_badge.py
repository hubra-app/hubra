"""The person's member badge on the account page.

One badge per person, not per club: the badge number belongs to the account
(``users.badge_code``) and stays the same in every club. Under it the badge
lists the person's memberships, each with that club's tier, kind of
membership and since when.

The number is random (not the account id), so it says nothing about how many
accounts there are and can be shown or printed without giving anything away.
"""

from __future__ import annotations

import secrets

from sqlalchemy import select

from hubra.core.extensions import db
from hubra.core.models.user import User

# Crockford base32 without the letters that look like digits (I, L, O, U).
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_TRIES = 5


def new_code() -> str:
    """A fresh badge number like ``HB-7K3M-Q9TX``."""
    raw = "".join(secrets.choice(_ALPHABET) for _ in range(8))
    return f"HB-{raw[:4]}-{raw[4:]}"


def ensure_code(user: User) -> str:
    """The account's badge number; given (and committed) on first use."""
    if user.badge_code:
        return user.badge_code
    for _ in range(_TRIES):
        code = new_code()
        taken = db.session.scalar(select(User.id).where(User.badge_code == code))
        if taken is None:
            user.badge_code = code
            db.session.commit()
            return code
    raise RuntimeError("Could not find a free badge number")


def _membership(club: dict) -> dict | None:
    from hubra.core.models.member import Member
    from hubra.core.models.tenant import Tenant
    from hubra.core.tenant.context import in_club

    def row(member: Member) -> dict:
        tier = member.tier
        return {
            "club": {
                "slug": club["tenant_slug"],
                "name": club["tenant_name"],
                "logoVersion": club.get("logo_version"),
            },
            "tier": {"name": tier.name, "color": tier.color} if tier else None,
            "membershipType": member.membership_type,
            "status": member.status,
            "joined": member.joined.isoformat() if member.joined else None,
            "until": member.membership_until.isoformat()
            if member.membership_until
            else None,
        }

    tenant = db.session.get(Tenant, club["tenant_id"]) if club["tenant_id"] else None
    if tenant is None:
        member = db.session.get(Member, club["member_id"])
        return row(member) if member else None
    with in_club(tenant):
        member = db.session.get(Member, club["member_id"])
        return row(member) if member else None


def memberships(user: User) -> list[dict]:
    """The person's memberships, one per club (tier, kind, since when)."""
    from hubra.core.auth.services import AuthService

    clubs = [c for c in AuthService.find_user_tenants(user.id) if c.get("member_id")]
    return [m for m in (_membership(c) for c in clubs) if m]


def badge_for(user: User) -> dict:
    """The badge: number, name, since when on Hubra, and the clubs."""
    from hubra.core.auth.mfa import qr_svg
    from hubra.core.services import google_wallet

    code = ensure_code(user)

    return {
        "code": code,
        # The badge number as a QR code, for a check-in or a scan at the door.
        "qrSvg": qr_svg(code),
        "name": f"{user.first_name} {user.last_name}".strip(),
        "avatarColor": user.avatar_color,
        "since": user.created_at.date().isoformat() if user.created_at else None,
        "memberships": memberships(user),
        # "Add to Google Wallet" is offered when the platform has it set up.
        "googleWallet": google_wallet.enabled(),
    }
