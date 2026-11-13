"""Token checks every backend runs on each request.

Registered by the app factory (hubra.core.app), not by the sign-in routes,
so a backend that serves only part of the API still refuses revoked or
outdated tokens and still sends a club's two-factor rule to SSO.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import g, jsonify, make_response
from flask_jwt_extended import (
    create_access_token,
    set_access_cookies,
    unset_jwt_cookies,
)
from sqlalchemy import select

from hubra.core.auth import lifetime, mfa, session_service
from hubra.core.extensions import db
from hubra.core.models.member import Member
from hubra.core.models.token import TokenBlocklist
from hubra.core.models.user import User
from hubra.core.tenant.context import current_tenant


def register_jwt_callbacks(jwt_manager) -> None:
    """Register token blocklist and user-lookup callbacks on *jwt_manager*."""

    @jwt_manager.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        # Impersonation ends at its deadline, whatever the token's own expiry.
        until = jwt_payload.get("impersonation_expires_at")
        if until is not None:
            try:
                deadline = datetime.fromisoformat(str(until))
            except ValueError:
                return True
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= deadline:
                return True
            # Platform staff can end a support session early (manage ›
            # Support-Zugriffe).
            support = jwt_payload.get("impersonation_session")
            if support and db.session.scalar(
                select(TokenBlocklist.id).where(
                    TokenBlocklist.jti == f"support:{support}"
                )
            ):
                return True
        # A refresh token that was rotated or revoked is refused even while
        # its session is alive. Rotated ones get a minute of grace so that
        # parallel tabs which refreshed together settle on their new tokens.
        if jwt_payload.get("type") == "refresh":
            row = db.session.execute(
                select(TokenBlocklist.type, TokenBlocklist.created_at).where(
                    TokenBlocklist.jti == jwt_payload["jti"]
                )
            ).first()
            if row is not None:
                if row.type != "refresh-rotated":
                    return True
                created = row.created_at
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) >= created + timedelta(seconds=60):
                    return True
        # The account sign-in this token comes from (SSO portal), if any:
        # ending it ends the club tokens it led to as well.
        account_sid = jwt_payload.get("account_sid")
        if account_sid is not None and session_service.is_account_session_revoked(
            int(account_sid)
        ):
            return True
        # Check Session by session ID (Redis-cached, covers access tokens)
        sid = jwt_payload.get("sid")
        if sid is not None:
            return session_service.is_session_revoked(int(sid))
        if account_sid is not None:
            return False
        # Fall back to TokenBlocklist for legacy tokens. Refresh tokens were
        # already checked above, grace and all.
        if jwt_payload.get("type") == "refresh":
            return False
        jti = jwt_payload["jti"]
        return (
            db.session.scalar(
                select(TokenBlocklist.id).where(TokenBlocklist.jti == jti)
            )
            is not None
        )

    @jwt_manager.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        identity = jwt_data["sub"]
        if isinstance(identity, str) and identity.startswith("user:"):
            user = db.session.get(User, int(identity[5:]))
            return user if token_still_valid(user, jwt_data) else None
        # A member id only means something in the club that issued the
        # token: refuse it in any other club (None -> 401 below).
        tenant = current_tenant()
        if (tenant.slug if tenant else None) != jwt_data.get("tenant_slug"):
            return None
        member = db.session.get(Member, int(identity))
        # Removed or switched off in this club: the session ends now, not
        # when the refresh token runs out.
        if member is None or member.archived_at is not None or member.is_blocked:
            return None
        if member.user is None:  # members from before accounts existed
            return member
        if not token_still_valid(member.user, jwt_data):
            return None
        # The club turned on "two-factor required" after this sign-in.
        if mfa.club_blocks(tenant, member, member.user):
            g.mfa_required_by_club = (member.user_id, jwt_data)
            return None
        return member

    @jwt_manager.user_lookup_error_loader
    def user_lookup_error_callback(_jwt_header, jwt_data):
        from flask import make_response as _make_response

        response = _make_response(
            jsonify({"error": "UNAUTHORIZED", "message": "User not found"}),
            401,
        )
        unset_jwt_cookies(response)
        return response


def club_requires_mfa(response):
    """A club session the club's two-factor rule now refuses.

    403 with its own code instead of a 401 (which the app answers with a
    refresh and a sign-out), and the club token is swapped for an account
    token: the person stays signed in on SSO, where the club app sends them
    to set two-factor up, and opens the club again afterwards.
    """
    blocked = g.get("mfa_required_by_club")
    if response.status_code != 401 or not blocked:
        return response
    user_id, jwt_data = blocked
    account_sid = jwt_data.get("account_sid")
    refused = make_response(
        jsonify(
            {
                "error": "MFA_REQUIRED_BY_CLUB",
                "message": "This club requires two-factor sign-in. "
                "Turn it on in your account first.",
            }
        ),
        403,
    )
    claims = {"user_id": user_id}
    if account_sid is not None:
        claims["account_sid"] = account_sid
    # The swapped account session ends when the club one would have.
    lifetime.carry(jwt_data, claims)
    set_access_cookies(
        refused,
        create_access_token(identity=f"user:{user_id}", additional_claims=claims),
    )
    lifetime.set_refresh(refused, f"user:{user_id}", claims)
    return refused


def token_still_valid(user: User | None, jwt_data: dict) -> bool:
    """False for a disabled account, or a token issued before the account
    ended all its sessions (password reset, password set by an admin)."""
    if user is None:
        return False
    if user.is_disabled:
        return False
    cutoff = user.tokens_valid_after
    if cutoff is None:
        return True
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    issued = datetime.fromtimestamp(int(jwt_data.get("iat", 0)), timezone.utc)
    return issued >= cutoff.replace(microsecond=0)
