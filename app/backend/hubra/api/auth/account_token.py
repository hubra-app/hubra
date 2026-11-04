"""The account token: what the manager portal runs on.

Platform routes (``require_global_permission``) used to accept whatever sat
in the standard JWT cookie.  All three portals share that cookie on the API
host, so opening a club put a *club* token there — and the platform routes
accepted it, because it carries a ``user_id`` claim too.  That let any
script running in the club app (a malicious plugin frontend, an XSS) drive
the manager API with a platform admin's session.

Now platform routes take only an *account* identity:

* the standard cookie, when it holds a ``user:<id>`` token (the SSO portal
  and manage before any club is opened), or
* the dedicated ``account_token`` cookie, set at sign-in and left alone by
  ``/auth/switch-tenant`` — so manage keeps working while a club is open,
  but a club token alone opens nothing.

The dedicated cookie is long-lived and checked server-side on every request
(account session revoked, account disabled, ``tokens_valid_after``), like a
refresh token.  Writes carry the double-submit header ``X-Account-CSRF``
matching the JS-readable ``csrf_account_token`` cookie.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import current_app, g, request
from flask_jwt_extended import create_access_token, decode_token

from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.user import User

ACCOUNT_COOKIE = "account_token"
ACCOUNT_CSRF_COOKIE = "csrf_account_token"
ACCOUNT_CSRF_HEADER = "X-Account-CSRF"
_LIFETIME = timedelta(days=30)


def issue(response, user: User, account_sid: int | None) -> None:
    """Set the account token (and its CSRF twin) on *response*."""
    claims: dict = {"user_id": user.id, "acct": True}
    if account_sid is not None:
        claims["account_sid"] = account_sid
    token = create_access_token(
        identity=f"user:{user.id}",
        additional_claims=claims,
        expires_delta=_LIFETIME,
    )
    csrf = decode_token(token).get("csrf") or ""
    secure = bool(current_app.config.get("JWT_COOKIE_SECURE", False))
    domain = current_app.config.get("JWT_COOKIE_DOMAIN") or None
    samesite = current_app.config.get("JWT_COOKIE_SAMESITE", "Lax")
    max_age = int(_LIFETIME.total_seconds())
    response.set_cookie(
        ACCOUNT_COOKIE,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite=samesite,
        domain=domain,
    )
    response.set_cookie(
        ACCOUNT_CSRF_COOKIE,
        value=csrf,
        max_age=max_age,
        httponly=False,  # the SPA reads it for the X-Account-CSRF header
        secure=secure,
        samesite=samesite,
        domain=domain,
    )


def clear(response) -> None:
    """Delete the account cookies (sign-out)."""
    domain = current_app.config.get("JWT_COOKIE_DOMAIN") or None
    response.delete_cookie(ACCOUNT_COOKIE, domain=domain)
    response.delete_cookie(ACCOUNT_CSRF_COOKIE, domain=domain)


def read_claims() -> dict | None:
    """The claims of the ``account_token`` cookie, or None without one.

    Signature and expiry are checked; revocation is not (callers decide
    whether they need it, ``verify_account_token`` does).
    """
    token = request.cookies.get(ACCOUNT_COOKIE)
    if not token:
        return None
    try:
        return decode_token(token)
    except Exception:  # expired, bad signature, wrong shape
        return None


def _token_still_valid(user: User | None, claims: dict) -> bool:
    from hubra.api.auth.routes import _token_still_valid as check

    return check(user, claims)


def verify_account_token() -> tuple[User, dict]:
    """The account identity of this request, or raise 401.

    Order: the dedicated ``account_token`` cookie; else the standard JWT
    when it holds a ``user:<id>`` identity.  A club token (member identity)
    is refused with ``ACCOUNT_TOKEN_REQUIRED``: platform routes never run
    on the token a club's scripts can reach.
    """
    claims = read_claims()
    if claims is not None and claims.get("acct") is True:
        # Writes need the double-submit header for this cookie.
        if (
            request.method not in ("GET", "HEAD", "OPTIONS")
            and current_app.config.get("JWT_COOKIE_CSRF_PROTECT", True)
            and request.headers.get(ACCOUNT_CSRF_HEADER) != claims.get("csrf")
        ):
            raise_error(401, "CSRF_ERROR", "Missing or wrong X-Account-CSRF header")
        account_sid = claims.get("account_sid")
        if account_sid is not None:
            from hubra.api.auth import session_service

            if session_service.is_account_session_revoked(int(account_sid)):
                raise_error(401, "UNAUTHORIZED", "This sign-in was ended")
        user = db.session.get(User, int(claims.get("user_id") or 0))
        if user is None or not _token_still_valid(user, claims):
            raise_error(401, "UNAUTHORIZED", "Token invalid or expired")
        g.account_claims = claims
        return user, claims

    # No (valid) dedicated cookie: the standard token, if it is an account one.
    from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

    try:
        verify_jwt_in_request()
    except Exception:
        raise_error(401, "UNAUTHORIZED", "Token invalid or expired")
    identity = get_jwt_identity()
    from hubra.api.auth.helpers import is_user_identity

    if not is_user_identity(identity):
        # A club token. The person may well be signed in — manage just needs
        # the account cookie, which sign-ins after this release set.
        raise_error(
            401,
            "ACCOUNT_TOKEN_REQUIRED",
            "This needs an account sign-in, not a club session. Sign in again.",
        )
    jwt_claims = get_jwt()
    user = db.session.get(User, int(identity[5:]))
    if user is None or not _token_still_valid(user, jwt_claims):
        raise_error(401, "UNAUTHORIZED", "Token invalid or expired")
    g.account_claims = jwt_claims
    return user, jwt_claims


# ── Step-up (sudo mode) ──────────────────────────────────────────────────────

SUDO_MINUTES = 10


def sudo_active(claims: dict) -> bool:
    """True while this account session confirmed its password (or code)
    within the last ``SUDO_MINUTES`` minutes."""
    account_sid = claims.get("account_sid")
    if account_sid is None:
        return False
    from hubra.core.models.account_session import AccountSession

    session = db.session.get(AccountSession, int(account_sid))
    if session is None or session.sudo_until is None:
        return False
    until = session.sudo_until
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) < until


def grant_sudo(claims: dict) -> datetime:
    """Mark this account session stepped-up for ``SUDO_MINUTES`` minutes."""
    account_sid = claims.get("account_sid")
    if account_sid is None:
        raise_error(
            403,
            "STEP_UP_REQUIRED",
            "This sign-in is too old for this action. Sign in again.",
        )
    from hubra.core.models.account_session import AccountSession

    session = db.session.get(AccountSession, int(account_sid))
    if session is None or session.revoked_at is not None:
        raise_error(401, "UNAUTHORIZED", "This sign-in was ended")
    until = datetime.now(timezone.utc) + timedelta(minutes=SUDO_MINUTES)
    session.sudo_until = until
    return until


def require_step_up(fn):
    """Decorator under ``require_global_permission``: the account session
    must have confirmed its password (POST /account/step-up) in the last few
    minutes.  For the actions that run code or open every club: installing
    plugins, restoring backups, rotating keys, impersonating.

    ``STEP_UP_ENFORCED`` (default on; off in tests) switches it globally.
    """
    from functools import wraps

    from flask import jsonify

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_app.config.get("STEP_UP_ENFORCED", True):
            return fn(*args, **kwargs)
        claims = getattr(g, "account_claims", None)
        if claims is None or not sudo_active(claims):
            return jsonify(
                {
                    "error": "STEP_UP_REQUIRED",
                    "message": "Confirm your password to do this",
                }
            ), 403
        return fn(*args, **kwargs)

    # API tokens never pass a step-up route (hubra.api.auth.api_tokens).
    wrapper._step_up = True
    return wrapper
