"""Managing API tokens (docs/api-tokens.md).

Club side, ``/api/v1/app/api-tokens`` (club session only; no API token ever
reaches these routes):

* ``GET  /scopes``      what the signed-in member may put on a token
* ``GET  /mine``        my personal tokens in this club
* ``POST /mine``        make one (two-factor + fresh step-up)
* ``DELETE /mine/<id>`` revoke one
* ``PATCH /mine/<id>``   rename, change scopes (adding a key: same checks as making)
* ``POST /mine/<id>/roll`` new secret, the old one ends after a grace period
* ``GET  /``            admins: every token of this club
* ``POST /club``        admins: a club integration token
* ``DELETE /<id>``      admins: revoke any token of this club
* ``PATCH /<id>``       admins: change a club token (never a member's own)
* ``POST /<id>/roll``   admins: roll a club token (never a member's own)
* ``PUT  /settings``    admins: let members make personal tokens

Platform side, ``/api/v1/platform/api-tokens`` (account sign-in only):

* ``GET /mine``, ``POST /mine``, ``DELETE /mine/<id>``: a platform admin's
  own read-only tokens
* ``GET /``, ``DELETE /<id>``: every token, for platform admins
"""

from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify, request
from flask_jwt_extended import get_jwt
from sqlalchemy import func, select

from hubra.core.auth import api_tokens, mfa
from hubra.core.auth.account_token import read_claims, sudo_active
from hubra.core.permissions import (
    _current_member,
    _get_member_permission_keys,
    held_roles,
    member_is_admin,
    require_admin,
    require_global_permission,
    require_member,
)
from hubra.core.extensions import db
from hubra.core.models.api_token import ApiToken
from hubra.core.models.tenant import GlobalAuditEntry
from hubra.core.tenant.context import current_tenant

api_tokens_bp = Blueprint("api_tokens_bp", __name__)
platform_api_tokens_bp = Blueprint("platform_api_tokens_bp", __name__)
# Answers a token about itself; its routes carry ``token_self``.
api_token_self_bp = Blueprint("api_token_self_bp", __name__)


def _error(status: int, code: str, message: str):
    return jsonify({"error": code, "message": message}), status


def _body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _maker_checks(user, claims: dict):
    """Two-factor on, a fresh step-up, no support session. None if fine."""
    if claims.get("impersonator_id") is not None:
        return _error(403, "IMPERSONATION_RESTRICTED", "Not during a support session")
    if user is None:
        return _error(401, "UNAUTHORIZED", "Sign in first")
    if not mfa.enabled(user):
        return _error(
            403,
            "MFA_SETUP_FIRST",
            "Turn on two-factor sign-in before making API tokens",
        )
    if current_app.config.get("STEP_UP_ENFORCED", True):
        account = read_claims() or {}
        if not (sudo_active(claims) or sudo_active(account)):
            return _error(403, "STEP_UP_REQUIRED", "Confirm your password to do this")
    return None


def _days(data: dict, maximum: int):
    days = data.get("days", api_tokens.DEFAULT_DAYS)
    if not isinstance(days, int) or isinstance(days, bool):
        return None
    if days not in api_tokens.LIFETIMES or days > maximum:
        return None
    return days


def _name(data: dict) -> str | None:
    name = data.get("name")
    if not isinstance(name, str):
        return None
    name = name.strip()
    return name if 1 <= len(name) <= 100 else None


def _scopes(data: dict, grantable: set[str]) -> list[str] | None:
    """The requested scopes: a list of keys, or the preset "read". Every
    key must be one the maker holds now. None if the request is invalid."""
    preset = data.get("preset")
    if preset is not None:
        if preset != "read":
            return None
        keys = {k for k in grantable if _is_read(k)}
        return sorted(keys) or None
    scopes = data.get("scopes")
    if not isinstance(scopes, list) or not scopes or len(scopes) > 300:
        return None
    if not all(isinstance(k, str) for k in scopes):
        return None
    keys = set(scopes)
    if not keys <= grantable:
        return None
    return sorted(keys)


def _is_read(key: str) -> bool:
    action = key.rsplit(".", 1)[-1]
    return action == "read" or action.startswith("read_")


def _ips(data: dict):
    try:
        return api_tokens.parse_allowed_ips(data.get("allowedIps")), None
    except ValueError:
        return None, _error(
            400, "VALIDATION_ERROR", "allowedIps: a list of up to 20 IP addresses or ranges"
        )


def _roll_params(data: dict, row: ApiToken, grantable: set[str], maximum: int):
    """(scopes, days, grace_hours) for a roll, or an error response."""
    grace = data.get("graceHours", api_tokens.DEFAULT_ROLL_GRACE_HOURS)
    if (
        not isinstance(grace, int)
        or isinstance(grace, bool)
        or grace not in api_tokens.ROLL_GRACE_HOURS
    ):
        return None, _error(400, "VALIDATION_ERROR", "graceHours: one of 0, 1, 24, 168")
    if "days" in data:
        days = _days(data, maximum)
        if days is None:
            return None, _error(400, "VALIDATION_ERROR", "days: not an allowed lifetime")
    else:
        created = api_tokens._aware(row.created_at)
        expires = api_tokens._aware(row.expires_at)
        span = max(1, round((expires - created).total_seconds() / 86400))
        allowed = [d for d in api_tokens.LIFETIMES if d <= maximum]
        days = min(allowed, key=lambda d: abs(d - span))
    # Rights may have shrunk since the token was made: never roll them on.
    scopes = sorted(set(row.scopes or ()) & grantable)
    if not scopes:
        return None, _error(
            409, "API_TOKEN_SCOPE", "You no longer hold any of this token's scopes"
        )
    return (scopes, days, grace), None


def _edit(row: ApiToken, grantable: set[str], user, claims: dict):
    """Change a token's name and/or scopes. Narrowing is always fine;
    adding a key needs the same checks as making a token, and only keys
    the person holds now. Returns an error response or None."""
    if row.oauth_client_id is not None:
        return _error(409, "OAUTH_GRANT", "An app's sign-in can only be ended")
    if not api_tokens.is_active(row):
        return _error(409, "API_TOKEN_INACTIVE", "Only an active token can be changed")
    data = _body()
    if "name" in data:
        name = _name(data)
        if name is None:
            return _error(400, "VALIDATION_ERROR", "name: 1 to 100 characters")
        row.name = name
    if "scopes" in data or "preset" in data:
        scopes = _scopes(data, grantable)
        if scopes is None:
            return _error(
                400,
                "VALIDATION_ERROR",
                "scopes: permission keys you hold yourself, or preset 'read'",
            )
        if row.kind == "platform" and not scopes:
            return _error(400, "VALIDATION_ERROR", "scopes: at least one key")
        if not set(scopes) <= set(row.scopes or ()):
            refusal = _maker_checks(user, claims)
            if refusal is not None:
                return refusal
        row.scopes = scopes
    return None


def _rolled(row: ApiToken, new: ApiToken, plaintext: str):
    body = api_tokens.to_json(new)
    body["token"] = plaintext  # shown once
    body["previous"] = api_tokens.to_json(row)
    return jsonify(body), 201


# ── Club side ───────────────────────────────────────────────────────────────


def _club_catalog() -> set[str]:
    from hubra.core.models.role import Permission

    return set(db.session.scalars(select(Permission.key)).all())


def _grantable(member) -> set[str]:
    if member_is_admin(member):
        return _club_catalog()
    if held_roles(member):
        return set(_get_member_permission_keys(member))
    return set()


def _member_name(member) -> str:
    return (getattr(member, "name", "") or "").strip()


def _club_row(token_id: int) -> ApiToken | None:
    tenant = current_tenant()
    row = db.session.get(ApiToken, token_id)
    if row is None or tenant is None or row.tenant_id != tenant.id:
        return None
    return row


def _active_count(**where) -> int:
    from datetime import datetime, timezone

    q = select(func.count(ApiToken.id)).where(
        ApiToken.revoked_at.is_(None),
        ApiToken.expires_at > datetime.now(timezone.utc),
        # App sign-ins (OAuth) have their own limit.
        ApiToken.oauth_client_id.is_(None),
    )
    for key, value in where.items():
        q = q.where(getattr(ApiToken, key) == value)
    return int(db.session.scalar(q) or 0)


def _audit_club(action: str, row: ApiToken, member) -> None:
    from hubra.core.utils import log_audit

    log_audit(member.id, action, "api_token", row.id, row.name)


def _make_club_token(kind: str, member):
    tenant = current_tenant()
    if tenant is None:
        return _error(400, "NO_CLUB", "Open a club first")
    user = getattr(member, "user", None)
    refusal = _maker_checks(user, get_jwt())
    if refusal is not None:
        return refusal
    admin = member_is_admin(member)
    if kind == "member" and not admin and not api_tokens.members_allowed(tenant):
        return _error(
            403,
            "API_TOKEN_DISABLED_BY_CLUB",
            "This club doesn't allow personal API tokens",
        )
    data = _body()
    name = _name(data)
    if name is None:
        return _error(400, "VALIDATION_ERROR", "name: 1 to 100 characters")
    days = _days(data, max(api_tokens.LIFETIMES))
    if days is None:
        return _error(400, "VALIDATION_ERROR", "days: one of 7, 30, 90, 365")
    scopes = _scopes(data, _grantable(member))
    if scopes is None:
        return _error(
            400,
            "VALIDATION_ERROR",
            "scopes: permission keys you hold yourself, or preset 'read'",
        )
    ips, ip_error = _ips(data)
    if ip_error is not None:
        return ip_error
    if kind == "member":
        if (
            _active_count(kind="member", tenant_id=tenant.id, member_id=member.id)
            >= api_tokens.MAX_PERSONAL_PER_MEMBER
        ):
            return _error(409, "API_TOKEN_LIMIT", "You have the most tokens allowed")
    elif _active_count(kind="club", tenant_id=tenant.id) >= api_tokens.MAX_CLUB_PER_CLUB:
        return _error(409, "API_TOKEN_LIMIT", "This club has the most tokens allowed")

    row, plaintext = api_tokens.make(
        kind=kind,
        user=user,
        name=name,
        scopes=scopes,
        days=days,
        tenant=tenant,
        member_id=member.id,
        created_by_name=_member_name(member),
        allowed_ips=ips,
    )
    _audit_club("api_token.create", row, member)
    db.session.commit()
    body = api_tokens.to_json(row)
    body["token"] = plaintext  # shown once
    return jsonify(body), 201


@api_tokens_bp.get("/scopes")
@require_member
def club_scopes():
    member = _current_member()
    grantable = sorted(_grantable(member))
    return jsonify(
        {
            "grantable": grantable,
            "read": [k for k in grantable if _is_read(k)],
            "isAdmin": member_is_admin(member),
            "membersAllowed": api_tokens.members_allowed(current_tenant()),
            "aiAllowed": api_tokens.ai_allowed(current_tenant()),
            "lifetimes": list(api_tokens.LIFETIMES),
        }
    ), 200


@api_tokens_bp.get("/mine")
@require_member
def my_club_tokens():
    member = _current_member()
    tenant = current_tenant()
    if tenant is None:
        return jsonify({"items": []}), 200
    rows = db.session.scalars(
        select(ApiToken)
        .where(
            ApiToken.kind == "member",
            ApiToken.tenant_id == tenant.id,
            ApiToken.member_id == member.id,
            ApiToken.oauth_client_id.is_(None),
        )
        .order_by(ApiToken.created_at.desc())
    ).all()
    return jsonify({"items": [api_tokens.to_json(r) for r in rows]}), 200


@api_tokens_bp.post("/mine")
@require_member
def make_my_club_token():
    return _make_club_token("member", _current_member())


@api_tokens_bp.delete("/mine/<int:token_id>")
@require_member
def revoke_my_club_token(token_id: int):
    member = _current_member()
    row = _club_row(token_id)
    if row is None or row.kind != "member" or row.member_id != member.id:
        return _error(404, "NOT_FOUND", "Token not found")
    api_tokens.revoke(row, _member_name(member))
    _audit_club("api_token.revoke", row, member)
    db.session.commit()
    return jsonify(api_tokens.to_json(row)), 200


def _roll_club(row: ApiToken, member):
    if row.oauth_client_id is not None:
        return _error(409, "OAUTH_GRANT", "An app's sign-in can only be ended")
    refusal = _maker_checks(getattr(member, "user", None), get_jwt())
    if refusal is not None:
        return refusal
    if not api_tokens.is_active(row):
        return _error(409, "API_TOKEN_INACTIVE", "Only an active token can be rolled")
    params, error = _roll_params(
        _body(), row, _grantable(member), max(api_tokens.LIFETIMES)
    )
    if error is not None:
        return error
    scopes, days, grace = params
    new, plaintext = api_tokens.roll(
        row, scopes=scopes, days=days, grace_hours=grace, by_name=_member_name(member)
    )
    _audit_club("api_token.roll", new, member)
    db.session.commit()
    return _rolled(row, new, plaintext)


@api_tokens_bp.post("/mine/<int:token_id>/roll")
@require_member
def roll_my_club_token(token_id: int):
    member = _current_member()
    row = _club_row(token_id)
    if row is None or row.kind != "member" or row.member_id != member.id:
        return _error(404, "NOT_FOUND", "Token not found")
    tenant = current_tenant()
    if not member_is_admin(member) and not api_tokens.members_allowed(tenant):
        return _error(
            403,
            "API_TOKEN_DISABLED_BY_CLUB",
            "This club doesn't allow personal API tokens",
        )
    return _roll_club(row, member)


@api_tokens_bp.patch("/mine/<int:token_id>")
@require_member
def edit_my_club_token(token_id: int):
    member = _current_member()
    row = _club_row(token_id)
    if row is None or row.kind != "member" or row.member_id != member.id:
        return _error(404, "NOT_FOUND", "Token not found")
    error = _edit(row, _grantable(member), getattr(member, "user", None), get_jwt())
    if error is not None:
        return error
    _audit_club("api_token.update", row, member)
    db.session.commit()
    return jsonify(api_tokens.to_json(row)), 200


@api_tokens_bp.get("/")
@require_admin
def club_tokens():
    tenant = current_tenant()
    if tenant is None:
        return jsonify({"items": [], "membersAllowed": False}), 200
    rows = db.session.scalars(
        select(ApiToken)
        .where(ApiToken.tenant_id == tenant.id)
        .order_by(ApiToken.created_at.desc())
    ).all()
    return jsonify(
        {
            "items": [api_tokens.to_json(r) for r in rows],
            "membersAllowed": api_tokens.members_allowed(tenant),
        }
    ), 200


@api_tokens_bp.post("/club")
@require_admin
def make_club_token():
    return _make_club_token("club", _current_member())


@api_tokens_bp.delete("/<int:token_id>")
@require_admin
def revoke_club_token(token_id: int):
    member = _current_member()
    row = _club_row(token_id)
    if row is None:
        return _error(404, "NOT_FOUND", "Token not found")
    api_tokens.revoke(row, _member_name(member))
    _audit_club("api_token.revoke", row, member)
    db.session.commit()
    return jsonify(api_tokens.to_json(row)), 200


@api_tokens_bp.patch("/<int:token_id>")
@require_admin
def edit_club_token(token_id: int):
    """Admins change club tokens; a member's own token they can only revoke."""
    member = _current_member()
    row = _club_row(token_id)
    if row is None or row.kind != "club":
        return _error(404, "NOT_FOUND", "Token not found")
    error = _edit(row, _grantable(member), getattr(member, "user", None), get_jwt())
    if error is not None:
        return error
    _audit_club("api_token.update", row, member)
    db.session.commit()
    return jsonify(api_tokens.to_json(row)), 200


@api_tokens_bp.post("/<int:token_id>/roll")
@require_admin
def roll_club_token(token_id: int):
    """Admins roll club tokens only: a member's personal token is theirs,
    and rolling it would hand its new secret to someone else."""
    member = _current_member()
    row = _club_row(token_id)
    if row is None or row.kind != "club":
        return _error(404, "NOT_FOUND", "Token not found")
    return _roll_club(row, member)


@api_tokens_bp.put("/settings")
@require_admin
def club_token_settings():
    """``{membersAllowed?, aiAllowed?}``: who may hold personal tokens, and
    whether AI assistants (the Claude connector) may read with tokens."""
    tenant = current_tenant()
    if tenant is None:
        return _error(400, "NO_CLUB", "Open a club first")
    data = _body()
    switches = {"membersAllowed": "members", "aiAllowed": "ai"}
    changes = {}
    for field, key in switches.items():
        if field in data:
            if not isinstance(data[field], bool):
                return _error(400, "VALIDATION_ERROR", f"{field}: true or false")
            changes[key] = data[field]
    if not changes:
        return _error(400, "VALIDATION_ERROR", "membersAllowed or aiAllowed")
    settings = dict(tenant.settings or {})
    before = dict(settings.get("api_tokens") or {})
    settings["api_tokens"] = {**before, **changes}
    tenant.settings = settings
    from hubra.core.utils import log_audit

    names = {"members": "api_token.members", "ai": "api_token.ai"}
    for key, value in changes.items():
        if bool(before.get(key)) == value:
            continue
        log_audit(
            _current_member().id,
            f"{names[key]}_{'on' if value else 'off'}",
            "club",
            tenant.id,
            tenant.name,
        )
    db.session.commit()
    return jsonify(
        {
            "membersAllowed": api_tokens.members_allowed(tenant),
            "aiAllowed": api_tokens.ai_allowed(tenant),
        }
    ), 200


# ── "Which token is this?" (for the token itself) ───────────────────────────


def _self_body():
    token = api_tokens.current()
    if token is None:
        return _error(401, "API_TOKEN_REQUIRED", "Send an API token")
    row = db.session.get(ApiToken, token["id"])
    if row is None:
        return _error(401, "API_TOKEN_INVALID", "API token invalid")
    body = api_tokens.to_json(row)
    body.pop("lastUsedIp", None)
    tenant = current_tenant() if row.kind != "platform" else None
    body["club"] = (
        {"slug": tenant.slug, "name": tenant.name} if tenant is not None else None
    )
    body["aiAllowed"] = api_tokens.ai_allowed(tenant) if tenant is not None else None
    body["app"] = None
    if row.oauth_client_id is not None:
        from hubra.core.models.oauth import OAuthClient

        client = db.session.get(OAuthClient, row.oauth_client_id)
        body["app"] = {"name": client.name, "verified": client.kind == "registered"} if client else None
    return jsonify(body), 200


@api_token_self_bp.get("/app/api-tokens/self")
@api_tokens.token_self
def club_token_self():
    return _self_body()


@api_token_self_bp.get("/platform/api-tokens/self")
@api_tokens.token_self
def platform_token_self():
    return _self_body()


# ── Platform side ───────────────────────────────────────────────────────────


def _platform_user():
    """The signed-in platform admin (account sign-in), or an error."""
    from hubra.core.auth.account_token import verify_account_token
    from hubra.core.permissions import get_user_global_permissions, staff_mfa_missing
    from hubra.core.errors import ApiError

    try:
        user, claims = verify_account_token()
    except ApiError as exc:
        return None, None, _error(exc.status, exc.code, exc.message)
    perms = get_user_global_permissions(user.id)
    if staff_mfa_missing(user) or not perms:
        return None, None, _error(403, "FORBIDDEN", "Platform admins only")
    return user, claims, None


def _platform_grantable(user) -> set[str]:
    from hubra.core.permissions import get_user_global_permissions
    from hubra.core.models.global_role import GlobalPermission

    perms = get_user_global_permissions(user.id)
    if "*" in perms:
        return set(db.session.scalars(select(GlobalPermission.key)).all()) | {
            "platform.diagnostics",
            "platform.settings",
        }
    return set(perms)


def _mcp_url() -> str:
    from hubra.core.services import platform_settings

    return platform_settings.get("mcp.url").strip().rstrip("/")


def _audit_platform(action: str, row: ApiToken, user) -> None:
    db.session.add(
        GlobalAuditEntry(
            actor_id=user.id,
            action=action,
            target_type="api_token",
            target_id=str(row.id),
            details={"name": row.name, "kind": row.kind, "scopes": row.scopes},
            ip_address=(request.remote_addr or "")[:45],
        )
    )


@platform_api_tokens_bp.get("/mine")
@api_tokens.no_api_tokens
def my_platform_tokens():
    user, _claims, error = _platform_user()
    if error is not None:
        return error
    rows = db.session.scalars(
        select(ApiToken)
        .where(
            ApiToken.kind == "platform",
            ApiToken.user_id == user.id,
            ApiToken.oauth_client_id.is_(None),
        )
        .order_by(ApiToken.created_at.desc())
    ).all()
    return jsonify(
        {
            "items": [api_tokens.to_json(r) for r in rows],
            "grantable": sorted(_platform_grantable(user)),
            "maxDays": api_tokens.PLATFORM_MAX_DAYS,
            "mcpUrl": _mcp_url(),
        }
    ), 200


@platform_api_tokens_bp.post("/mine")
@api_tokens.no_api_tokens
def make_my_platform_token():
    user, claims, error = _platform_user()
    if error is not None:
        return error
    refusal = _maker_checks(user, claims or {})
    if refusal is not None:
        return refusal
    data = _body()
    name = _name(data)
    if name is None:
        return _error(400, "VALIDATION_ERROR", "name: 1 to 100 characters")
    days = _days(data, api_tokens.PLATFORM_MAX_DAYS)
    if days is None:
        return _error(400, "VALIDATION_ERROR", "days: 7 or 30")
    scopes = data.get("scopes") or ["platform.diagnostics"]
    if not isinstance(scopes, list) or not all(isinstance(k, str) for k in scopes):
        return _error(400, "VALIDATION_ERROR", "scopes: a list of permission keys")
    if not set(scopes) <= _platform_grantable(user):
        return _error(400, "VALIDATION_ERROR", "scopes: only permissions you hold")
    ips, ip_error = _ips(data)
    if ip_error is not None:
        return ip_error
    if (
        _active_count(kind="platform", user_id=user.id)
        >= api_tokens.MAX_PLATFORM_PER_ADMIN
    ):
        return _error(409, "API_TOKEN_LIMIT", "You have the most tokens allowed")
    row, plaintext = api_tokens.make(
        kind="platform",
        user=user,
        name=name,
        scopes=scopes,
        days=days,
        created_by_name=f"{user.first_name} {user.last_name}".strip() or user.email,
        allowed_ips=ips,
    )
    _audit_platform("api_token.create", row, user)
    db.session.commit()
    body = api_tokens.to_json(row)
    body["token"] = plaintext  # shown once
    return jsonify(body), 201


@platform_api_tokens_bp.delete("/mine/<int:token_id>")
@api_tokens.no_api_tokens
def revoke_my_platform_token(token_id: int):
    user, _claims, error = _platform_user()
    if error is not None:
        return error
    row = db.session.get(ApiToken, token_id)
    if row is None or row.kind != "platform" or row.user_id != user.id:
        return _error(404, "NOT_FOUND", "Token not found")
    api_tokens.revoke(row, row.created_by_name)
    _audit_platform("api_token.revoke", row, user)
    db.session.commit()
    return jsonify(api_tokens.to_json(row)), 200


@platform_api_tokens_bp.patch("/mine/<int:token_id>")
@api_tokens.no_api_tokens
def edit_my_platform_token(token_id: int):
    user, claims, error = _platform_user()
    if error is not None:
        return error
    row = db.session.get(ApiToken, token_id)
    if row is None or row.kind != "platform" or row.user_id != user.id:
        return _error(404, "NOT_FOUND", "Token not found")
    error = _edit(row, _platform_grantable(user), user, claims or {})
    if error is not None:
        return error
    _audit_platform("api_token.update", row, user)
    db.session.commit()
    return jsonify(api_tokens.to_json(row)), 200


@platform_api_tokens_bp.post("/mine/<int:token_id>/roll")
@api_tokens.no_api_tokens
def roll_my_platform_token(token_id: int):
    user, claims, error = _platform_user()
    if error is not None:
        return error
    refusal = _maker_checks(user, claims or {})
    if refusal is not None:
        return refusal
    row = db.session.get(ApiToken, token_id)
    if row is None or row.kind != "platform" or row.user_id != user.id:
        return _error(404, "NOT_FOUND", "Token not found")
    if row.oauth_client_id is not None:
        return _error(409, "OAUTH_GRANT", "An app's sign-in can only be ended")
    if not api_tokens.is_active(row):
        return _error(409, "API_TOKEN_INACTIVE", "Only an active token can be rolled")
    params, error = _roll_params(
        _body(), row, _platform_grantable(user), api_tokens.PLATFORM_MAX_DAYS
    )
    if error is not None:
        return error
    scopes, days, grace = params
    new, plaintext = api_tokens.roll(
        row, scopes=scopes, days=days, grace_hours=grace, by_name=row.created_by_name
    )
    _audit_platform("api_token.roll", new, user)
    db.session.commit()
    return _rolled(row, new, plaintext)


@platform_api_tokens_bp.get("/")
@require_global_permission("platform.settings")
@api_tokens.no_api_tokens
def all_tokens():
    rows = db.session.scalars(
        select(ApiToken).order_by(ApiToken.created_at.desc()).limit(500)
    ).all()
    from hubra.core.models.tenant import Tenant

    tenant_ids = {r.tenant_id for r in rows if r.tenant_id}
    clubs = {
        t.id: t
        for t in db.session.scalars(select(Tenant).where(Tenant.id.in_(tenant_ids)))
    } if tenant_ids else {}
    items = []
    for r in rows:
        item = api_tokens.to_json(r)
        item["tenantId"] = r.tenant_id
        item["userId"] = r.user_id
        club = clubs.get(r.tenant_id)
        item["club"] = {"slug": club.slug, "name": club.name} if club else None
        items.append(item)
    return jsonify({"items": items}), 200


@platform_api_tokens_bp.delete("/<int:token_id>")
@require_global_permission("platform.settings")
@api_tokens.no_api_tokens
def revoke_any_token(token_id: int):
    row = db.session.get(ApiToken, token_id)
    if row is None:
        return _error(404, "NOT_FOUND", "Token not found")
    user = g.system_user
    name = f"{user.first_name} {user.last_name}".strip() or user.email
    api_tokens.revoke(row, f"{name} (Hubra)")
    _audit_platform("api_token.revoke", row, user)
    db.session.commit()
    return jsonify(api_tokens.to_json(row)), 200
