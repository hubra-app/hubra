"""Account routes that read or change club data need a club member.

A sign-in without a club (the SSO portal) is a ``User``, and its id is not a
member id. Those routes used ``current_user.id`` as the member id inside
whatever club the request named (``X-Tenant-Slug`` or ``/api/<slug>/v1``),
so they read and changed another club's member with the same number:
invoices, sessions and devices, mail forwarding.
"""

from __future__ import annotations

from flask import request
from flask_jwt_extended import current_user, verify_jwt_in_request

from hubra.core.errors import api_error

# View names on account_bp whose data lives in one club.
CLUB_MEMBER_VIEWS = frozenset(
    {
        "get_account_invoices",
        "get_account_groups",
        "get_account_mail_settings",
        "update_account_mail_settings",
        "list_account_sessions",
        "revoke_account_session",
        "rename_account_session",
        "revoke_all_other_sessions",
        "list_account_devices",
        "rename_account_device",
        "revoke_account_device",
    }
)


def club_member_only():
    """``before_request`` for account_bp: refuse a User on club-member routes."""
    from hubra.core.models.member import Member

    view = (request.endpoint or "").rsplit(".", 1)[-1]
    if view not in CLUB_MEMBER_VIEWS:
        return None
    try:
        verify_jwt_in_request()
    except Exception:
        return None  # the view's own decorator answers 401
    if current_user is not None and not isinstance(current_user, Member):
        return api_error("FORBIDDEN", "No member profile in this tenant", 403)
    return None
