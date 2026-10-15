"""Auth blueprint — login, logout, refresh, and account endpoints.

Registered in create_app() under:
  auth_bp    → /api/v1/auth
  account_bp → /api/v1/account
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from argon2 import PasswordHasher as _PasswordHasher
from argon2.exceptions import VerifyMismatchError as _VerifyMismatchError
from flask import Blueprint, current_app, jsonify, make_response, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    current_user,
    get_jwt,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    set_refresh_cookies,
    unset_jwt_cookies,
)
from sqlalchemy import select

from vollbuild.api.auth.services import (
    AuthService,
    AccountService,
    compute_fingerprint,
    _enforce_password_strength,
    _extract_browser_family,
    _extract_platform,
    _EMAIL_RE,
)
from vollbuild.api.auth import session_service
from vollbuild.api.permissions import (
    require_password_changed,
    _get_member_permission_keys,
    member_is_admin,
)
from vollbuild.core.errors import api_error, raise_error
from vollbuild.core.extensions import db, limiter

from vollbuild.core.models.token import TokenBlocklist
from vollbuild.core.models.device_session import Session
from vollbuild.core.models.member import Member
from vollbuild.core.models.user import User
from vollbuild.core.models.user_tenant import UserTenant
from vollbuild.core.schemas.finance import InvoiceSchema
from vollbuild.core.schemas.group import GroupSchema
from vollbuild.core.schemas.member import MemberSchema
from vollbuild.core.services import email as email_svc
from vollbuild.core.services.email import _get_sso_base_url
from vollbuild.api.notifications.services import create_notification
from vollbuild.core.tenant.context import current_tenant

_log = logging.getLogger(__name__)

# Pre-computed hash used to burn time in forgot-password when the email
# doesn't match any account, preventing timing-based account enumeration.
_ph = _PasswordHasher()
_DUMMY_HASH = _ph.hash("timing-dummy-value")

auth_bp = Blueprint("auth_bp", __name__)
account_bp = Blueprint("account_bp", __name__)

_member_schema = MemberSchema()
_invoice_schema = InvoiceSchema()
_group_schema = GroupSchema()


def _set_remembered_email_cookie(response, email: str) -> None:
    """Set the remembered_email cookie so the frontend can prefill the login form.

    Cross-subdomain correctness: the frontend SPA (cos.vollbuild.ch) reads this
    via document.cookie, so it must (a) be scoped to the shared registrable
    domain (.vollbuild.ch) — host-only would never reach the frontend, and
    (b) be HttpOnly=False so JS can read it. SameSite=Lax is safe (same-site
    subdomain navigation) and Secure mirrors the JWT cookies (HTTPS upstream).
    """
    response.set_cookie(
        "remembered_email",
        value=email,
        max_age=30 * 24 * 3600,
        httponly=False,
        samesite="Lax",
        secure=current_app.config.get("JWT_COOKIE_SECURE", False),
        domain=current_app.config.get("JWT_COOKIE_DOMAIN") or None,
    )


def _clear_remembered_email_cookie(response) -> None:
    """Delete remembered_email using the SAME domain/path it was set with."""
    response.delete_cookie(
        "remembered_email",
        domain=current_app.config.get("JWT_COOKIE_DOMAIN") or None,
    )


# ── JWT callbacks (called from create_app) ────────────────────────────────────


def register_jwt_callbacks(jwt_manager) -> None:
    """Register token blocklist and user-lookup callbacks on *jwt_manager*."""

    @jwt_manager.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        # Check Session by session ID (Redis-cached, covers access tokens)
        sid = jwt_payload.get("sid")
        if sid is not None:
            return session_service.is_session_revoked(int(sid))
        # Fall back to TokenBlocklist for refresh tokens and legacy tokens

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
            return db.session.get(User, int(identity[5:]))
        return db.session.get(Member, int(identity))

    @jwt_manager.user_lookup_error_loader
    def user_lookup_error_callback(_jwt_header, jwt_data):
        from flask import make_response as _make_response

        response = _make_response(
            jsonify({"error": "UNAUTHORIZED", "message": "User not found"}),
            401,
        )
        unset_jwt_cookies(response)
        return response


# ── POST /auth/login ──────────────────────────────────────────────────────────


@auth_bp.post("/login")
@limiter.limit("5 per minute")
def login():
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    keep_signed_in = bool(body.get("keepSignedIn", True))

    user: User | None = None
    member: Member | None = None
    try:
        user = AuthService.authenticate_user(email, password)
        member = AuthService.resolve_member(user.id)

        if user.is_disabled:
            raise_error(
                403,
                "ACCOUNT_DISABLED",
                "Account has been disabled by an administrator",
            )
        _locked = user.locked_until
        if _locked is not None:
            if _locked.tzinfo is None:
                _locked = _locked.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) < _locked:
                raise_error(
                    403,
                    "ACCOUNT_LOCKED",
                    "Account is temporarily locked due to too many failed login attempts. Try again later.",
                )
    except Exception:
        member = AuthService.authenticate(email, password)
        user = db.session.scalar(select(User).where(User.email == email))
        if user is None and member.user_id:
            user = db.session.get(User, member.user_id)

    if member is None and user is None:
        raise_error(401, "UNAUTHORIZED", "Invalid credentials")

    if member is None and user is not None:
        tenants = AuthService.find_user_tenants(user.id)
        if tenants:
            return jsonify({"requiresTenantSelection": True, "tenants": tenants}), 200

        additional_claims = {"user_id": user.id}
        access_token = create_access_token(
            identity=f"user:{user.id}",
            additional_claims=additional_claims,
        )
        refresh_token = create_refresh_token(
            identity=f"user:{user.id}",
            additional_claims=additional_claims,
        )
        response = make_response(
            jsonify(
                noTenant=True,
                user={"email": user.email, "name": user.name},
            ),
            200,
        )
        set_access_cookies(response, access_token)
        refresh_max_age = 30 * 24 * 3600 if keep_signed_in else 24 * 3600
        set_refresh_cookies(response, refresh_token, max_age=refresh_max_age)
        _set_remembered_email_cookie(response, email)
        return response

    raw_ua = request.headers.get("User-Agent", "")[:512]
    fp = compute_fingerprint(request.headers)
    new_device, session_id = AuthService.record_login(
        member,
        request.remote_addr or "",
        raw_ua,
        fingerprint=fp,
        browser_family=_extract_browser_family(request.headers),
        platform=_extract_platform(request.headers),
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    if new_device:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        if member.private_email_verified:
            email_svc.send_new_device_login(
                member.email,
                member.name,
                request.remote_addr or "",
                request.headers.get("User-Agent", "")[:512],
                ts,
                lang=getattr(member, "language", "de-CH") or "de-CH",
            )
        else:
            _log.info(
                "skip_new_device_login member_id=%s — email not verified", member.id
            )
        create_notification(
            member_id=member.id,
            kind="warning",
            title="New device login",
            msg=f"Your account was accessed from a new device or location at {ts}. "
            f"If this wasn't you, go to Settings → Account → Sessions to revoke it.",
        )

    session = db.session.get(Session, session_id)
    tenant = current_tenant()
    additional_claims = {"sid": session_id} if session else {}
    if user:
        additional_claims["user_id"] = user.id
    if tenant:
        additional_claims["tenant_slug"] = tenant.slug

    access_token = create_access_token(
        identity=str(member.id),
        additional_claims=additional_claims,
    )
    refresh_token = create_refresh_token(
        identity=str(member.id),
        additional_claims=additional_claims,
    )

    response = make_response(
        jsonify(
            mustChangePassword=member.must_change_password,
            member=_member_schema.dump(member),
            tenant_slug=tenant.slug if tenant else None,
        ),
        200,
    )
    set_access_cookies(response, access_token)
    refresh_max_age = 30 * 24 * 3600 if keep_signed_in else 24 * 3600
    set_refresh_cookies(response, refresh_token, max_age=refresh_max_age)
    _set_remembered_email_cookie(response, email)
    return response


# ── POST /auth/signup ─────────────────────────────────────────────────────────


@auth_bp.post("/signup")
@limiter.limit("3 per minute")
def signup():
    """Create a new global User account with no tenant membership.

    The user can then request a tenant from the manager portal or be
    invited to an existing tenant by an admin.
    """
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    keep_signed_in = bool(body.get("keepSignedIn", True))

    if not name or not email or not password:
        raise_error(400, "VALIDATION_ERROR", "name, email, and password are required")

    _enforce_password_strength(password)

    if not _EMAIL_RE.match(email):
        raise_error(400, "VALIDATION_ERROR", "Invalid email address")

    existing = db.session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise_error(409, "CONFLICT", "An account with this email already exists")

    user = User(email=email, name=name)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    additional_claims = {"user_id": user.id}
    access_token = create_access_token(
        identity=f"user:{user.id}",
        additional_claims=additional_claims,
    )
    refresh_token = create_refresh_token(
        identity=f"user:{user.id}",
        additional_claims=additional_claims,
    )
    response = make_response(
        jsonify(
            noTenant=True,
            user={"email": user.email, "name": user.name},
        ),
        201,
    )
    set_access_cookies(response, access_token)
    refresh_max_age = 30 * 24 * 3600 if keep_signed_in else 24 * 3600
    set_refresh_cookies(response, refresh_token, max_age=refresh_max_age)
    _set_remembered_email_cookie(response, email)
    return response


# ── POST /auth/refresh ────────────────────────────────────────────────────────


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
@limiter.limit("20 per minute")
def refresh():
    identity = get_jwt_identity()
    AuthService.check_locked(identity)

    # Verify the identity's subject still exists — if not, clear cookies
    if isinstance(identity, str) and identity.startswith("user:"):
        user = db.session.get(User, int(identity[5:]))
        if user is None:
            response = make_response(
                jsonify({"error": "UNAUTHORIZED", "message": "User not found"}), 401
            )
            unset_jwt_cookies(response)
            _clear_remembered_email_cookie(response)
            return response
    else:
        member = db.session.get(Member, int(identity))
        if member is None:
            response = make_response(
                jsonify({"error": "UNAUTHORIZED", "message": "Member not found"}), 401
            )
            unset_jwt_cookies(response)
            _clear_remembered_email_cookie(response)
            return response

    # Preserve sid claim from refresh token if present
    refresh_claims = get_jwt()
    sid = refresh_claims.get("sid")

    if sid is not None:
        from flask import current_app

        from vollbuild.core.tasks.session_tasks import update_session_activity

        if current_app.config.get("TESTING"):
            update_session_activity.run(int(sid))
        else:
            update_session_activity.delay(int(sid))

    additional_claims = {"sid": sid} if sid is not None else {}
    access_token = create_access_token(
        identity=identity,
        additional_claims=additional_claims,
    )
    response = make_response(jsonify(ok=True), 200)
    set_access_cookies(response, access_token)
    return response


# ── POST /auth/logout ─────────────────────────────────────────────────────────


@auth_bp.post("/logout")
@jwt_required()
def logout():
    claims = get_jwt()
    sid = claims.get("sid")

    # Revoke the Session if present
    if sid is not None:
        session = db.session.get(Session, int(sid))
        if session is not None and session.revoked_at is None:
            session.revoked_at = datetime.now(timezone.utc)
            session.revoked_reason = "logout"
            session_service._invalidate_session_cache(session.id)
    else:
        access_jti = claims["jti"]
        AuthService.block_token(access_jti, "access")

    data = request.get_json(silent=True) or {}
    refresh_token = data.get("refreshToken")
    if refresh_token:
        try:
            from flask_jwt_extended import decode_token

            decoded = decode_token(refresh_token)
            AuthService.block_token(decoded["jti"], "refresh")
        except Exception:
            _log.debug("Logout: refresh token not revocable", exc_info=True)

    db.session.commit()
    response = make_response("", 204)
    unset_jwt_cookies(response)
    _clear_remembered_email_cookie(response)
    return response


# ── POST /auth/switch-tenant ──────────────────────────────────────────────────


@auth_bp.post("/switch-tenant")
@jwt_required()
def switch_tenant():
    """Switch the active tenant for the current user.

    Expects JSON body with ``tenantSlug``. Verifies the user belongs to the
    target tenant via UserTenant, then reissues JWTs scoped to that tenant.
    """
    body = request.get_json(silent=True) or {}
    target_slug = body.get("tenantSlug", "").strip()
    if not target_slug:
        return api_error("VALIDATION_ERROR", "tenantSlug is required", 400)

    claims = get_jwt()
    user_id = claims.get("user_id")
    if not user_id:
        return api_error("UNAUTHORIZED", "No user_id in token", 401)

    from vollbuild.core.models.tenant import Tenant

    tenant = db.session.scalar(select(Tenant).where(Tenant.slug == target_slug))
    if tenant is None:
        return api_error("NOT_FOUND", "Tenant not found", 404)

    membership = db.session.scalar(
        select(UserTenant).where(
            UserTenant.user_id == user_id,
            UserTenant.tenant_id == tenant.id,
        )
    )
    if membership is None:
        return api_error("FORBIDDEN", "You are not a member of this tenant", 403)

    from vollbuild.core.tenant.context import set_search_path

    set_search_path(tenant.id)
    member = db.session.scalar(
        select(Member).where(
            Member.user_id == user_id,
            Member.archived_at.is_(None),
        )
    )
    if member is None:
        return api_error("FORBIDDEN", "No member profile in this tenant", 403)

    sid = claims.get("sid")
    additional_claims = {"user_id": user_id, "tenant_slug": target_slug}
    if sid is not None:
        additional_claims["sid"] = sid

    access_token = create_access_token(
        identity=str(member.id),
        additional_claims=additional_claims,
    )
    refresh_token = create_refresh_token(
        identity=str(member.id),
        additional_claims=additional_claims,
    )

    response = make_response(
        jsonify(
            tenantSlug=target_slug,
            member=_member_schema.dump(member),
        ),
        200,
    )
    set_access_cookies(response, access_token)
    set_refresh_cookies(response, refresh_token, max_age=30 * 24 * 3600)
    return response


# ── POST /auth/forgot-password ────────────────────────────────────────────────


@auth_bp.post("/forgot-password")
@limiter.limit("3 per hour")
def forgot_password():
    body = request.get_json(silent=True) or {}
    email = body.get("email", "").strip().lower()

    if not email:
        return jsonify({"ok": True}), 200

    result = AuthService.create_password_reset(email)
    if result is None:
        # Burn time equivalent to a real password hash verification so that
        # response timing doesn't reveal whether the account exists.
        try:
            _ph.verify(_DUMMY_HASH, "dummy-check")
        except _VerifyMismatchError:
            pass
        return jsonify({"ok": True}), 200

    raw_token, member = result

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    reset_url = f"{_get_sso_base_url()}/reset-password#token={raw_token}"
    email_svc.send_password_reset(
        member.email,
        member.name,
        reset_url,
        lang=getattr(member, "language", "de-CH") or "de-CH",
    )

    return jsonify({"ok": True}), 200


# ── POST /auth/reset-password ─────────────────────────────────────────────────


@auth_bp.post("/reset-password")
@limiter.limit("10 per minute")
def reset_password():
    body = request.get_json(silent=True) or {}
    raw_token = body.get("token", "").strip()
    new_password = body.get("password", "")

    member = AuthService.reset_password(raw_token, new_password)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    if member.private_email_verified:
        email_svc.send_password_changed(member.email, member.name)
    else:
        _log.info("skip_password_changed member_id=%s — email not verified", member.id)

    return jsonify({"ok": True}), 200


# ── GET /account ──────────────────────────────────────────────────────────────


@account_bp.get("/")
@require_password_changed
def get_account():
    from vollbuild.core.models.user import User

    if isinstance(current_user, User):
        return jsonify(
            {
                "noTenant": True,
                "user": {"email": current_user.email, "name": current_user.name},
            }
        ), 200
    return jsonify(_member_schema.dump(current_user)), 200


# ── GET /account/permissions ─────────────────────────────────────────────────


@account_bp.get("/permissions")
@jwt_required()
def get_my_permissions():
    """Return the current user's permission keys (or ['*'] for admins).

    Also includes ``is_superadmin`` flag and ``impersonation`` context
    when the user is being impersonated by a system admin.
    """
    member = current_user
    claims = get_jwt()

    # Check for superadmin via user_id claim
    user_id = claims.get("user_id")
    is_superadmin = False
    if user_id:
        from vollbuild.core.models.user import User

        user = db.session.get(User, int(user_id))
        is_superadmin = user is not None and user.is_superadmin

    # Global permissions (manager portal RBAC)
    from vollbuild.api.permissions import get_user_global_permissions

    global_perms: list[str] = []
    global_roles: list[str] = []
    if user_id:
        global_perms = sorted(get_user_global_permissions(int(user_id)))
        from vollbuild.core.models.global_role import GlobalRole, UserGlobalRole

        global_roles = list(
            db.session.execute(
                select(GlobalRole.name)
                .join(UserGlobalRole, UserGlobalRole.role_id == GlobalRole.id)
                .where(UserGlobalRole.user_id == int(user_id))
            )
            .scalars()
            .all()
        )

    # Check for impersonation context
    impersonation = None
    impersonator_id = claims.get("impersonator_id")
    if impersonator_id is not None:
        impersonation = {
            "is_impersonating": True,
            "impersonator_id": impersonator_id,
            "impersonator_user_id": claims.get("impersonator_user_id"),
            "tenant_slug": claims.get("tenant_slug"),
            "reason": claims.get("impersonation_reason"),
            "expires_at": claims.get("impersonation_expires_at"),
            "restricted_actions": ["delete_tenant", "change_plan"],
        }

    if member_is_admin(member):
        return jsonify(
            {
                "is_admin": True,
                "is_superadmin": is_superadmin,
                "permissions": ["*"],
                "impersonation": impersonation,
                "global_permissions": global_perms,
                "global_roles": global_roles,
            }
        ), 200
    roles = getattr(member, "roles", None)
    if not roles:
        return jsonify(
            {
                "is_admin": False,
                "is_superadmin": is_superadmin,
                "permissions": [],
                "impersonation": impersonation,
                "global_permissions": global_perms,
                "global_roles": global_roles,
            }
        ), 200
    keys = _get_member_permission_keys(member)
    return jsonify(
        {
            "is_admin": False,
            "is_superadmin": is_superadmin,
            "permissions": sorted(keys),
            "impersonation": impersonation,
            "global_permissions": global_perms,
            "global_roles": global_roles,
        }
    ), 200


@account_bp.get("/my-tenants")
@jwt_required()
def get_my_tenants():
    """Return all tenants the current user belongs to.

    Uses ``AuthService.find_user_tenants`` to resolve the User's
    UserTenant memberships. Returns a list of
    ``{tenant_id, tenant_slug, tenant_name, member_id}``.
    """
    claims = get_jwt()
    user_id = claims.get("user_id")
    if not user_id:
        return jsonify({"tenants": []}), 200

    tenants = AuthService.find_user_tenants(int(user_id))
    return jsonify({"tenants": tenants}), 200


# ── PATCH /account ────────────────────────────────────────────────────────────


@account_bp.patch("/")
@jwt_required()
def update_account():
    body = request.get_json(silent=True) or {}

    allowed = {
        "name",
        "first_name",
        "last_name",
        "email",
        "password",
        "avatar",
        "avatar_color",
        "profile_note",
        "language",
    }
    updates = {k: v for k, v in body.items() if k in allowed}

    member = current_user  # type: Member
    member, new_password = AccountService.update_account(member, updates)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    if new_password:
        from sqlalchemy import select as _sel

        from vollbuild.core.models.managed_mail import ManagedMailAddress as _MMA

        _addr = db.session.scalar(
            _sel(_MMA).where(_MMA.owner_type == "member", _MMA.owner_id == member.id)
        )
        if _addr and _addr.wildduck_user_id:
            from vollbuild.core.tasks.wildduck import sync_wildduck_password

            sync_wildduck_password.delay(member.id)

    return jsonify(_member_schema.dump(member)), 200


# ── POST /account/change-password ────────────────────────────────────────────


@account_bp.post("/change-password")
@jwt_required()
@limiter.limit("10 per minute")
def change_password():
    body = request.get_json(silent=True) or {}
    current_password = body.get("currentPassword", "")
    new_password = body.get("newPassword", "")

    member = current_user  # type: Member
    AccountService.change_password(member, current_password, new_password)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    from sqlalchemy import select as _sel

    from vollbuild.core.models.managed_mail import ManagedMailAddress as _MMA

    _addr = db.session.scalar(
        _sel(_MMA).where(_MMA.owner_type == "member", _MMA.owner_id == member.id)
    )
    if _addr and _addr.wildduck_user_id:
        from vollbuild.core.tasks.wildduck import sync_wildduck_password

        sync_wildduck_password.delay(member.id)

    if member.private_email_verified:
        email_svc.send_password_changed(
            member.email,
            member.name,
            lang=getattr(member, "language", "de-CH") or "de-CH",
        )
    else:
        _log.info("skip_password_changed member_id=%s — email not verified", member.id)

    return jsonify({"ok": True}), 200


# ── GET /account/invoices ────────────────────────────────────────────────────


@account_bp.get("/invoices")
@require_password_changed
def get_account_invoices():
    member = current_user  # type: Member
    invoices = AccountService.get_invoices(member.id)
    return jsonify([_invoice_schema.dump(inv) for inv in invoices]), 200


# ── GET /account/groups ──────────────────────────────────────────────────────


@account_bp.get("/groups")
@require_password_changed
def get_account_groups():
    member = current_user  # type: Member
    groups = AccountService.get_groups(member)
    return jsonify([_group_schema.dump(grp) for grp in groups]), 200


# ── GET /account/mail-settings ───────────────────────────────────────────────


@account_bp.get("/mail-settings")
@require_password_changed
def get_account_mail_settings():
    from vollbuild.api.features.services import FeatureFlagService

    mail_disabled = not FeatureFlagService.is_enabled("mail")

    from sqlalchemy import select as _sel

    from vollbuild.core.models.managed_mail import ManagedMailAddress as _MMA

    member = current_user  # type: Member
    addr = db.session.scalar(
        _sel(_MMA).where(_MMA.owner_type == "member", _MMA.owner_id == member.id)
    )
    return jsonify(
        forwarding_enabled=addr.forwarding_enabled if addr else False,
        mailbox_enabled=addr is not None and not mail_disabled,
        private_email_verified=member.private_email_verified,
        mail_disabled=mail_disabled,
    ), 200


# ── PATCH /account/mail-settings ─────────────────────────────────────────────


@account_bp.patch("/mail-settings")
@require_password_changed
def update_account_mail_settings():
    from vollbuild.api.features.services import FeatureFlagService

    if not FeatureFlagService.is_enabled("mail"):
        return api_error("FEATURE_DISABLED", "Mail feature is disabled", 409)

    body = request.get_json(silent=True) or {}
    member = current_user  # type: Member

    allowed = {"forwarding_enabled"}
    updates = {k: v for k, v in body.items() if k in allowed}

    if not updates:
        return api_error("VALIDATION_ERROR", "No valid fields provided", 400)

    AccountService.update_mail_settings(member, updates)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    from sqlalchemy import select as _sel

    from vollbuild.core.models.managed_mail import ManagedMailAddress as _MMA

    addr = db.session.scalar(
        _sel(_MMA).where(_MMA.owner_type == "member", _MMA.owner_id == member.id)
    )
    if addr:
        from vollbuild.core.tasks.wildduck import provision_member_mail

        provision_member_mail.delay(member.id)

    return jsonify(
        forwarding_enabled=addr.forwarding_enabled if addr else False,
        mailbox_enabled=addr is not None,
        private_email_verified=member.private_email_verified,
    ), 202


# ── POST /account/request-email-verification ─────────────────────────────────


@account_bp.post("/request-email-verification")
@jwt_required()
def request_email_verification():
    member = current_user  # type: Member
    raw_token = AccountService.create_email_verification_token(member)

    db.session.commit()

    verify_url = f"{_get_sso_base_url()}/verify-email#token={raw_token}"
    email_svc.send_email_verification(
        member.email,
        member.name,
        verify_url,
        lang=getattr(member, "language", "de-CH") or "de-CH",
    )
    _log.info(
        "email_verification_requested member_id=%s to_email=%s", member.id, member.email
    )

    return jsonify({"ok": True}), 202


# ── POST /account/verify-email ─────────────────────────────────────────────────


@account_bp.post("/verify-email")
def verify_email():
    body = request.get_json(silent=True) or {}
    raw_token = body.get("token", "").strip()
    if not raw_token:
        return api_error("VALIDATION_ERROR", "token is required", 400)
    member = AccountService.verify_email(raw_token)
    db.session.commit()

    _log.info("email_verification_confirmed member_id=%s", member.id)
    return jsonify({"ok": True, "verified": True}), 200


# ── GET /account/sessions ─────────────────────────────────────────────────────


@account_bp.get("/sessions")
@jwt_required()
def list_account_sessions():
    member = current_user  # type: Member
    include_revoked = request.args.get("include_revoked", "0") == "1"
    sessions = session_service.list_sessions(member.id, include_revoked=include_revoked)
    current_sid = get_jwt().get("sid")
    return (
        jsonify(
            [
                {
                    **session_service.serialize_session(s),
                    "current": str(s.id) == str(current_sid) if current_sid else False,
                }
                for s in sessions
            ]
        ),
        200,
    )


# ── DELETE /account/sessions/<id> ─────────────────────────────────────────────


@account_bp.delete("/sessions/<int:session_id>")
@jwt_required()
def revoke_account_session(session_id: int):
    member = current_user  # type: Member
    session = session_service.revoke_session(session_id, member.id)
    if session is None:
        raise_error(404, "NOT_FOUND", "Session not found or already revoked")
    db.session.commit()
    return jsonify({"ok": True}), 200


# ── PATCH /account/sessions/<id> ──────────────────────────────────────────────


@account_bp.patch("/sessions/<int:session_id>")
@jwt_required()
def rename_account_session(session_id: int):
    member = current_user  # type: Member
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    if name is not None:
        name = name.strip()[:100] or None
    session = session_service.get_session(session_id, member.id)
    if session is None:
        raise_error(404, "NOT_FOUND", "Session not found")
    # Rename applies to the Device, not the Session
    device = session_service.rename_device(session.device_id, member.id, name)
    if device is None:
        raise_error(404, "NOT_FOUND", "Device not found")
    db.session.commit()
    current_sid = get_jwt().get("sid")
    return (
        jsonify(
            {
                **session_service.serialize_session(session),
                "current": str(session.id) == str(current_sid)
                if current_sid
                else False,
            }
        ),
        200,
    )


# ── POST /account/sessions/revoke-all ─────────────────────────────────────────


@account_bp.post("/sessions/revoke-all")
@jwt_required()
def revoke_all_other_sessions():
    member = current_user  # type: Member
    current_sid = get_jwt().get("sid")
    body = request.get_json(silent=True) or {}
    include_current = body.get("includeCurrent", False)

    if include_current:
        count = session_service.revoke_all_including_current(member.id)
    else:
        count = session_service.revoke_all_other_sessions(member.id, int(current_sid))

    db.session.commit()
    return jsonify({"ok": True, "revoked": count}), 200


# ── GET /account/devices ──────────────────────────────────────────────────────


@account_bp.get("/devices")
@jwt_required()
def list_account_devices():
    member = current_user  # type: Member
    devices = session_service.list_devices(member.id)
    return jsonify(devices), 200


# ── PATCH /account/devices/<id> ───────────────────────────────────────────────


@account_bp.patch("/devices/<int:device_id>")
@jwt_required()
def rename_account_device(device_id: int):
    member = current_user  # type: Member
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    if name is not None:
        name = name.strip()[:100] or None
    device = session_service.rename_device(device_id, member.id, name)
    if device is None:
        raise_error(404, "NOT_FOUND", "Device not found")
    db.session.commit()
    return jsonify(session_service.serialize_device(device)), 200


# ── DELETE /account/devices/<id> ──────────────────────────────────────────────


@account_bp.delete("/devices/<int:device_id>")
@jwt_required()
def revoke_account_device(device_id: int):
    member = current_user  # type: Member
    count = session_service.revoke_device_sessions(device_id, member.id)
    if count == 0:
        raise_error(404, "NOT_FOUND", "Device not found or no active sessions")
    db.session.commit()
    return jsonify({"ok": True, "revoked": count}), 200
