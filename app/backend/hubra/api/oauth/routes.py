"""OAuth for outside apps (docs/oauth.md; logic in hubra/core/auth/oauth.py).

Public, for apps (RFC 6749 / 7591 / 7009 / 8414 / 9728):

* ``GET  /.well-known/oauth-authorization-server``  server metadata
* ``POST /api/v1/global/oauth/token``     codes and refresh tokens
* ``POST /api/v1/global/oauth/register``  self-registration (Claude connector)
* ``POST /api/v1/global/oauth/revoke``    an app ends its sign-in
* ``GET  /api/v1/global/oauth/resource``  the connector's resource metadata
* ``GET  /.well-known/openid-configuration``  OpenID Connect discovery
* ``GET  /api/v1/global/oauth/jwks``      the ID token keys
* ``GET|POST /api/v1/global/oauth/userinfo``  who signed in (bearer token)

For the SSO portal (account sign-in):

* ``GET  /api/v1/global/oauth/authorize``  what the consent page shows
* ``POST /api/v1/global/oauth/authorize``  allow or deny; answers where to go
* ``GET  /api/v1/global/oauth/grants``     my apps
* ``DELETE /api/v1/global/oauth/grants/<id>``

For manage (``/api/v1/platform/oauth``, platform.settings): the apps and
the signing keys. For club admins (``/api/v1/app/oauth``): the club's own
sign-in apps (docs/oidc.md).
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request
from sqlalchemy import func, select

from hubra.core.auth import api_tokens, mfa
from hubra.core.auth import oauth, oidc
from hubra.core.auth.oauth import OAuthError
from hubra.core.extensions import db, limiter
from hubra.core.models.api_token import ApiToken
from hubra.core.models.oauth import OAuthClient, RESOURCES
from hubra.core.models.tenant import GlobalAuditEntry, Tenant
from hubra.core.permissions import require_admin, require_global_permission
from hubra.core.timeutil import as_utc

oauth_metadata_bp = Blueprint("oauth_metadata_bp", __name__)
oauth_bp = Blueprint("oauth_bp", __name__)
platform_oauth_bp = Blueprint("platform_oauth_bp", __name__)
club_oauth_bp = Blueprint("club_oauth_bp", __name__)


def _error(status: int, code: str, message: str):
    return jsonify({"error": code, "message": message}), status


def _oauth_error(exc: OAuthError):
    resp = jsonify({"error": exc.error, "error_description": exc.description})
    resp.status_code = exc.status
    resp.headers["Cache-Control"] = "no-store"
    if exc.status == 401:
        resp.headers["WWW-Authenticate"] = 'Basic realm="hubra"'
    return resp


def _no_store(body: dict, status: int = 200):
    resp = jsonify(body)
    resp.status_code = status
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Pragma"] = "no-cache"
    return resp


def _body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _name(user) -> str:
    return f"{user.first_name} {user.last_name}".strip() or user.email


# ── Metadata ────────────────────────────────────────────────────────────────


@oauth_metadata_bp.get("/.well-known/oauth-authorization-server")
@api_tokens.no_api_tokens
def server_metadata():
    resp = jsonify(oauth.server_metadata())
    resp.headers["Cache-Control"] = "public, max-age=300"
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@oauth_metadata_bp.get("/.well-known/openid-configuration")
@api_tokens.no_api_tokens
def openid_configuration():
    resp = jsonify(oidc.discovery())
    resp.headers["Cache-Control"] = "public, max-age=300"
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@oauth_bp.get("/jwks")
@api_tokens.no_api_tokens
def jwks():
    body = oidc.jwks()
    db.session.commit()  # the first key, when it was just made
    resp = jsonify(body)
    resp.headers["Cache-Control"] = "public, max-age=300"
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@oauth_bp.route("/userinfo", methods=["GET", "POST"])
@api_tokens.no_api_tokens
@limiter.limit("120 per minute")
def userinfo():
    """OpenID Connect userinfo: the claims of the bearer token's sign-in,
    as they are now. ApiTokenWsgi leaves the token for this route."""
    raw = request.environ.get(api_tokens.USERINFO_ENVIRON_KEY)
    if raw is None:
        header = request.headers.get("Authorization", "")
        raw = header[len("Bearer ") :].strip() if header.startswith("Bearer ") else None
    if raw is None:
        resp = _no_store({"error": "invalid_request"}, 401)
        resp.headers["WWW-Authenticate"] = 'Bearer realm="hubra"'
        return resp
    body, problem = oidc.userinfo(raw)
    db.session.commit()
    if body is None:
        status = 403 if problem == "insufficient_scope" else 401
        resp = _no_store({"error": problem}, status)
        resp.headers["WWW-Authenticate"] = f'Bearer realm="hubra", error="{problem}"'
        return resp
    return _no_store(body)


@oauth_bp.get("/resource")
@api_tokens.no_api_tokens
def resource_metadata():
    """For the connector's /.well-known/oauth-protected-resource."""
    meta = oauth.resource_metadata()
    if meta is None:
        return _error(404, "NOT_SET_UP", "The Claude connector isn't set up (mcp.url)")
    resp = jsonify(meta)
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


# ── App endpoints ───────────────────────────────────────────────────────────


@oauth_bp.post("/token")
@api_tokens.no_api_tokens
@limiter.limit("60 per minute")
def token():
    form = request.form
    try:
        client = oauth.authenticate_client(form, request.headers)
        grant = form.get("grant_type")
        if grant == "authorization_code":
            return _no_store(oauth.exchange_code(client, form))
        if grant == "refresh_token":
            return _no_store(oauth.refresh(client, form))
        raise OAuthError("unsupported_grant_type", "authorization_code or refresh_token")
    except OAuthError as exc:
        db.session.rollback()
        return _oauth_error(exc)


@oauth_bp.post("/revoke")
@api_tokens.no_api_tokens
@limiter.limit("60 per minute")
def revoke():
    try:
        client = oauth.authenticate_client(request.form, request.headers)
    except OAuthError as exc:
        return _oauth_error(exc)
    oauth.revoke_token(client, request.form.get("token") or "")
    return _no_store({})


def _register_error(message: str, error: str = "invalid_client_metadata"):
    return _no_store({"error": error, "error_description": message}, 400)


@oauth_bp.post("/register")
@api_tokens.no_api_tokens
@limiter.limit("10 per hour")
def register():
    """RFC 7591 for the Claude connector: an app registers itself, may only
    read through the connector, and the person sees it as not checked by
    Hubra, with the address it returns to."""
    if not oauth.dynamic_allowed() or oauth.mcp_resource() is None:
        return _register_error("Self-registration is off", "access_denied")
    data = _body()
    uris = data.get("redirect_uris")
    if not isinstance(uris, list) or not 1 <= len(uris) <= 10:
        return _register_error("redirect_uris: 1 to 10 addresses", "invalid_redirect_uri")
    for u in uris:
        problem = oauth.redirect_uri_problem(u, dynamic=True)
        if problem:
            return _register_error(problem, "invalid_redirect_uri")
    method = data.get("token_endpoint_auth_method") or "client_secret_basic"
    if method not in oauth.AUTH_METHODS:
        return _register_error("token_endpoint_auth_method: none, client_secret_basic or client_secret_post")
    grants = data.get("grant_types") or ["authorization_code", "refresh_token"]
    if not isinstance(grants, list) or not set(grants) <= {"authorization_code", "refresh_token"}:
        return _register_error("grant_types: authorization_code and refresh_token only")
    responses = data.get("response_types") or ["code"]
    if responses != ["code"]:
        return _register_error("response_types: code only")
    name = data.get("client_name")
    if not isinstance(name, str) or not name.strip():
        name = "MCP-App"
    name = " ".join(name.split())[:100]
    client_uri = data.get("client_uri")
    if not (isinstance(client_uri, str) and client_uri.startswith("https://") and len(client_uri) <= 500):
        client_uri = None

    oauth.cleanup_dynamic()
    count = db.session.scalar(
        select(func.count(OAuthClient.id)).where(OAuthClient.kind == "dynamic")
    )
    if int(count or 0) >= oauth.MAX_DYNAMIC_CLIENTS:
        db.session.commit()
        return _register_error("Too many self-registered apps", "temporarily_unavailable")
    client, secret = oauth.make_client(
        kind="dynamic",
        name=name,
        redirect_uris=uris,
        resources=["mcp"],
        scopes=["read"],
        confidential=method != "none",
        client_uri=client_uri,
        created_by_name="Self-registered",
    )
    db.session.commit()
    body = {
        "client_id": client.client_id,
        "client_id_issued_at": int(client.created_at.timestamp()),
        "client_name": client.name,
        "redirect_uris": client.redirect_uris,
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": method,
        "scope": "read",
    }
    if client_uri:
        body["client_uri"] = client_uri
    if secret:
        body["client_secret"] = secret
        body["client_secret_expires_at"] = 0
    return _no_store(body, 201)


# ── Consent (SSO portal) ────────────────────────────────────────────────────


def _account():
    """(user, claims) of the account sign-in, or an error response."""
    from hubra.core.auth.account_token import verify_account_token
    from hubra.core.errors import ApiError

    try:
        user, claims = verify_account_token()
    except ApiError as exc:
        # Fixed texts, never the exception's own (CodeQL).
        if exc.code == "CSRF_ERROR":
            return None, None, _error(401, "CSRF_ERROR", "Missing or wrong X-Account-CSRF header")
        return None, None, _error(401, "UNAUTHORIZED", "Sign in first")
    if claims.get("impersonator_id") is not None:
        return None, None, _error(403, "IMPERSONATION_RESTRICTED", "Not during a support session")
    return user, claims, None


def _request_or_error(args):
    """(request dict, None) or (None, JSON for the consent page). A bad
    request answers 200 with ``problem`` (and ``redirect`` when the error
    may go back to the app), so the page can show it."""
    try:
        return oauth.check_request(args), None
    except OAuthError as exc:
        body = {"error": exc.error, "message": exc.description}
        if getattr(exc, "redirectable", False):
            body["redirect"] = oauth.with_params(
                exc.redirect_uri,  # type: ignore[attr-defined]
                error=exc.error,
                error_description=exc.description,
                state=getattr(exc, "state", None),
                iss=oauth.issuer(),
            )
        return None, (jsonify({"problem": body}), 200)


def _days() -> dict:
    return {
        "club": list(oauth.CLUB_DAYS),
        "platform": list(oauth.PLATFORM_DAYS),
        "defaultClub": oauth.DEFAULT_CLUB_DAYS,
        "defaultPlatform": oauth.DEFAULT_PLATFORM_DAYS,
    }


def _identity_club(user, req: dict) -> dict | None:
    """For a club's own sign-in app: the club, and whether this person is
    an active member who may sign in there."""
    tenant = req.get("tenant")
    if tenant is None:
        return None
    found = oidc.club_member(tenant, user.id)
    return {
        "slug": tenant.slug,
        "name": tenant.name,
        "available": found is not None,
        "reason": None if found is not None else "NOT_MEMBER",
        "memberId": found[0]["member_id"] if found is not None else None,
    }


def _choices(user, req: dict) -> dict:
    """The clubs (and the platform) this person may let the app read."""
    from hubra.core.auth.services import AuthService
    from hubra.core.permissions import get_user_global_permissions, staff_mfa_missing

    if req["mode"] == "identity":
        club = _identity_club(user, req)
        if club is not None:
            club.pop("memberId")
        return {"clubs": [], "platform": None, "club": club, "days": _days()}

    has_mfa = mfa.enabled(user)
    ai = req["resource_kind"] == "mcp"
    clubs = []
    for t in AuthService.find_user_tenants(user.id):
        tenant = db.session.get(Tenant, t["tenant_id"])
        if tenant is None or not t.get("member_id"):
            continue
        admin = t.get("admin_level") in ("owner", "admin")
        reason = None
        if not admin and not api_tokens.members_allowed(tenant):
            reason = "MEMBERS_OFF"
        elif ai and not api_tokens.ai_allowed(tenant):
            reason = "AI_OFF"
        elif (t.get("mfa_required") or "write" in req["scopes"]) and not has_mfa:
            reason = "MFA_SETUP_FIRST"
        clubs.append(
            {
                "slug": tenant.slug,
                "name": tenant.name,
                "isAdmin": admin,
                "available": reason is None,
                "reason": reason,
            }
        )
    platform = None
    perms = get_user_global_permissions(user.id)
    if perms:
        reason = None
        if staff_mfa_missing(user) or not has_mfa:
            reason = "MFA_SETUP_FIRST"
        # Always read-only, whatever the app asked for.
        platform = {"available": reason is None, "reason": reason}
    return {"clubs": clubs, "platform": platform, "club": None, "days": _days()}


def _remembered(user, req: dict) -> bool:
    """A sign-in-only app this person already allowed (same or more
    claims, still running): signing in again needs no new question."""
    if req["mode"] != "identity":
        return False
    rows = db.session.scalars(
        select(ApiToken).where(
            ApiToken.oauth_client_id == req["client"].id,
            ApiToken.user_id == user.id,
            ApiToken.kind == "identity",
            ApiToken.revoked_at.is_(None),
            ApiToken.expires_at > datetime.now(timezone.utc),
        )
    ).all()
    wanted = set(req["oidc"])
    return any(wanted <= set((r.oauth_scope or "").split()) for r in rows)


def _send_back(req: dict, error: str, message: str):
    """A problem the app hears about (OpenID prompt=none)."""
    return jsonify(
        {
            "problem": {
                "error": error,
                "message": message,
                "redirect": oauth.with_params(
                    req["redirect_uri"],
                    error=error,
                    state=req["state"],
                    iss=oauth.issuer(),
                ),
            }
        }
    ), 200


def _auth_time(claims: dict):
    """When the person signed in to this account session (ID token
    ``auth_time``), if known."""
    sid = claims.get("account_sid")
    if sid is None:
        return None
    from hubra.core.models.account_session import AccountSession

    session = db.session.get(AccountSession, int(sid))
    return session.created_at if session is not None else None


def _client_json(client: OAuthClient, redirect_uri: str | None = None) -> dict:
    from urllib.parse import urlsplit

    host = urlsplit(redirect_uri).hostname if redirect_uri else None
    return {
        "name": client.name,
        "description": client.description,
        "clientUri": client.client_uri,
        # Registered by a platform admin, so Hubra knows who it is.
        "verified": client.kind == "registered",
        "kind": client.kind,
        "redirectHost": host,
    }


@oauth_bp.get("/authorize")
@api_tokens.no_api_tokens
def consent_info():
    req, err = _request_or_error(request.args)
    if err is not None:
        return err
    silent = "none" in req["prompt"]
    user, _claims, error = _account()
    if error is not None:
        if silent:
            return _send_back(req, "login_required", "Not signed in")
        # The page sends the person to sign in first; the app is shown
        # already, so they know why.
        body, status = error
        payload = body.get_json()
        payload["client"] = _client_json(req["client"], req["redirect_uri"])
        return jsonify(payload), status
    choices = _choices(user, req)
    remembered = "consent" not in req["prompt"] and _remembered(user, req)
    if remembered and choices["club"] is not None and not choices["club"]["available"]:
        remembered = False
    if silent and not remembered:
        return _send_back(req, "consent_required", "The person has to agree first")
    return jsonify(
        {
            "client": _client_json(req["client"], req["redirect_uri"]),
            "mode": req["mode"],
            "resource": req["resource_kind"],
            "scopes": req["scopes"],
            "oidc": req["oidc"],
            # Allowed before: the page answers for the person at once.
            "remembered": remembered,
            "user": {"name": _name(user), "email": user.email},
            **choices,
        }
    ), 200


@oauth_bp.post("/authorize")
@api_tokens.no_api_tokens
@limiter.limit("30 per minute")
def consent():
    """``{params: {...the authorize query}, allow: bool, club?: slug,
    platform?: true, days?: int}`` → ``{redirect}``."""
    data = _body()
    params = data.get("params")
    if not isinstance(params, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in params.items()
    ):
        return _error(400, "VALIDATION_ERROR", "params: the authorize query")
    req, err = _request_or_error(params)
    if err is not None:
        return err
    user, claims, error = _account()
    if error is not None:
        return error
    back = {"state": req["state"], "iss": oauth.issuer()}
    if data.get("allow") is not True:
        return jsonify(
            {
                "redirect": oauth.with_params(
                    req["redirect_uri"],
                    error="access_denied",
                    error_description="The person said no",
                    **back,
                )
            }
        ), 200

    choices = _choices(user, req)
    slug = data.get("club")
    days = data.get("days")
    tenant = None
    member_id = None
    if req["mode"] == "identity":
        # Sign in with Hubra: nothing to read, no club to pick.
        club = _identity_club(user, req)
        if club is not None:
            if not club["available"]:
                return _error(403, "NOT_MEMBER", "Only members of this club sign in here")
            tenant = req["tenant"]
            member_id = club["memberId"]
        kind = "identity"
        allowed_days = (oidc.IDENTITY_DAYS,)
        days = oidc.IDENTITY_DAYS
        scopes = []
    elif data.get("platform") is True:
        platform = choices["platform"]
        if platform is None or not platform["available"]:
            return _error(403, platform["reason"] if platform else "FORBIDDEN", "Not for the platform")
        kind = "platform"
        allowed_days = oauth.PLATFORM_DAYS
        from hubra.api.api_tokens.routes import _platform_grantable

        scopes = sorted(_platform_grantable(user))
    elif isinstance(slug, str):
        club = next((c for c in choices["clubs"] if c["slug"] == slug), None)
        if club is None:
            return _error(404, "NOT_FOUND", "You aren't in this club")
        if not club["available"]:
            return _error(403, club["reason"], "This club doesn't allow it")
        tenant = db.session.scalar(select(Tenant).where(Tenant.slug == slug))
        from hubra.core.auth.services import AuthService

        member_id = next(
            t["member_id"]
            for t in AuthService.find_user_tenants(user.id)
            if t["tenant_id"] == tenant.id
        )
        kind = "member"
        allowed_days = oauth.CLUB_DAYS
        scopes = oauth.club_scope_keys(req["scopes"])
    else:
        return _error(400, "VALIDATION_ERROR", "club or platform")
    if days is None:
        days = allowed_days[-1]
    if not isinstance(days, int) or isinstance(days, bool) or days not in allowed_days:
        return _error(400, "VALIDATION_ERROR", f"days: one of {', '.join(map(str, allowed_days))}")
    if not scopes and kind != "identity":
        return _error(403, "FORBIDDEN", "Nothing to read")
    active = db.session.scalar(
        select(func.count(ApiToken.id)).where(
            ApiToken.user_id == user.id,
            ApiToken.oauth_client_id.is_not(None),
            ApiToken.kind != "identity",
            ApiToken.revoked_at.is_(None),
            ApiToken.expires_at > datetime.now(timezone.utc),
        )
    )
    if kind != "identity" and int(active or 0) >= oauth.MAX_GRANTS_PER_USER:
        return _error(409, "OAUTH_LIMIT", "You have the most app sign-ins allowed; end one first")
    code = oauth.make_code(
        req,
        user=user,
        kind=kind,
        tenant=tenant,
        member_id=member_id,
        scopes=scopes,
        days=days,
        created_by_name=_name(user),
        auth_time=_auth_time(claims),
    )
    db.session.commit()
    return jsonify(
        {"redirect": oauth.with_params(req["redirect_uri"], code=code, **back)}
    ), 200


# ── My apps (SSO account page) ──────────────────────────────────────────────


def _grant_json(row: ApiToken, clients: dict, clubs: dict) -> dict:
    client = clients.get(row.oauth_client_id)
    club = clubs.get(row.tenant_id)
    item = api_tokens.to_json(row)
    item.pop("lastUsedIp", None)
    item["app"] = _client_json(client) if client else None
    item["club"] = {"slug": club.slug, "name": club.name} if club else None
    item["resourceKind"] = oauth.resource_kind(row.resource)
    item["canWrite"] = row.kind not in ("platform", "identity") and any(
        not oauth._is_read(k) for k in row.scopes or []
    )
    # Sign in with Hubra only: the app reads nothing, it knows who you are.
    item["signIn"] = row.kind == "identity"
    item["claims"] = [
        s for s in (row.oauth_scope or "").split() if s in oidc.OIDC_SCOPES and s != "openid"
    ]
    item.pop("scopes", None)
    return item


def grants_json(rows: list[ApiToken]) -> list[dict]:
    client_ids = {r.oauth_client_id for r in rows}
    tenant_ids = {r.tenant_id for r in rows if r.tenant_id}
    clients = (
        {c.id: c for c in db.session.scalars(select(OAuthClient).where(OAuthClient.id.in_(client_ids)))}
        if client_ids
        else {}
    )
    clubs = (
        {t.id: t for t in db.session.scalars(select(Tenant).where(Tenant.id.in_(tenant_ids)))}
        if tenant_ids
        else {}
    )
    return [_grant_json(r, clients, clubs) for r in rows]


@oauth_bp.get("/grants")
@api_tokens.no_api_tokens
def my_grants():
    user, _claims, error = _account()
    if error is not None:
        return error
    rows = db.session.scalars(
        select(ApiToken)
        .where(
            ApiToken.user_id == user.id,
            ApiToken.oauth_client_id.is_not(None),
            ApiToken.revoked_at.is_(None),
            ApiToken.expires_at > datetime.now(timezone.utc),
        )
        .order_by(ApiToken.created_at.desc())
    ).all()
    return jsonify({"items": grants_json(list(rows))}), 200


@oauth_bp.delete("/grants/<int:token_id>")
@api_tokens.no_api_tokens
def end_my_grant(token_id: int):
    user, _claims, error = _account()
    if error is not None:
        return error
    row = db.session.get(ApiToken, token_id)
    if row is None or row.user_id != user.id or row.oauth_client_id is None:
        return _error(404, "NOT_FOUND", "Not found")
    oauth.end_grant(row, _name(user))
    db.session.commit()
    return jsonify({"ok": True}), 200


# ── Apps (manage) ───────────────────────────────────────────────────────────


def _app_json(client: OAuthClient, grants: int = 0, clubs: dict | None = None) -> dict:
    def iso(v):
        v = as_utc(v)
        return v.isoformat() if v else None

    return {
        "id": client.id,
        "clientId": client.client_id,
        "kind": client.kind,
        "name": client.name,
        "description": client.description,
        "clientUri": client.client_uri,
        "redirectUris": list(client.redirect_uris or []),
        "confidential": bool(client.secret_hash),
        "secretLast4": client.secret_last4,
        "resources": list(client.resources or []),
        "scopes": list(client.scopes or []),
        "createdByName": client.created_by_name,
        "createdAt": iso(client.created_at),
        "lastUsedAt": iso(client.last_used_at),
        "disabledAt": iso(client.disabled_at),
        "activeGrants": grants,
        "signIn": "openid" in (client.scopes or []),
        "club": _club_ref(client, clubs),
    }


def _club_ref(client: OAuthClient, clubs: dict | None) -> dict | None:
    if client.tenant_id is None:
        return None
    tenant = (clubs or {}).get(client.tenant_id) or db.session.get(Tenant, client.tenant_id)
    return {"slug": tenant.slug, "name": tenant.name} if tenant is not None else None


def _audit_platform(action: str, client: OAuthClient) -> None:
    db.session.add(
        GlobalAuditEntry(
            actor_id=g.system_user.id,
            action=action,
            target_type="oauth_client",
            target_id=str(client.id),
            details={"name": client.name, "kind": client.kind},
            ip_address=(request.remote_addr or "")[:45],
        )
    )


def _app_fields(data: dict, *, partial: bool):
    """Validated fields for a registered app, or (None, error)."""
    out: dict = {}
    if not partial or "name" in data:
        name = data.get("name")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
            return None, _error(400, "VALIDATION_ERROR", "name: 1 to 100 characters")
        out["name"] = name.strip()
    if "description" in data:
        desc = data.get("description") or ""
        if not isinstance(desc, str) or len(desc) > 500:
            return None, _error(400, "VALIDATION_ERROR", "description: up to 500 characters")
        out["description"] = desc.strip()
    if "clientUri" in data:
        uri = data.get("clientUri") or None
        if uri is not None and not (isinstance(uri, str) and uri.startswith("https://") and len(uri) <= 500):
            return None, _error(400, "VALIDATION_ERROR", "clientUri: an https address")
        out["client_uri"] = uri
    if not partial or "redirectUris" in data:
        uris = data.get("redirectUris")
        if not isinstance(uris, list) or not 1 <= len(uris) <= 10:
            return None, _error(400, "VALIDATION_ERROR", "redirectUris: 1 to 10 addresses")
        uris = [str(u).strip() for u in uris]
        for u in uris:
            problem = oauth.redirect_uri_problem(u, dynamic=False)
            if problem:
                return None, _error(400, "VALIDATION_ERROR", problem)
        out["redirect_uris"] = uris
    if not partial or "resources" in data:
        res = data.get("resources")
        if res is None:
            res = ["api"]
        if not isinstance(res, list) or not set(res) <= set(RESOURCES):
            return None, _error(400, "VALIDATION_ERROR", "resources: api and/or mcp")
        out["resources"] = sorted(set(res))
    if not partial or "scopes" in data:
        scopes = data.get("scopes") or ["read"]
        if not isinstance(scopes, list) or not set(scopes) <= {*oauth.SCOPES, "openid"}:
            return None, _error(400, "VALIDATION_ERROR", "scopes: read, write, openid")
        out["scopes"] = sorted(set(scopes))
    return out, None


def _app_shape_error(resources: list, scopes: list):
    """An app reads (API or connector, with "read") and/or signs people in
    ("openid")."""
    reads = bool(resources)
    if reads and "read" not in scopes:
        return _error(400, "VALIDATION_ERROR", "An app that reads needs the read scope")
    if not reads and set(scopes) & set(oauth.SCOPES):
        return _error(400, "VALIDATION_ERROR", "read and write need the API or the connector")
    if not reads and "openid" not in scopes:
        return _error(400, "VALIDATION_ERROR", "Pick what the app may do: read, or sign people in")
    if "mcp" in resources and "openid" in scopes:
        return _error(400, "VALIDATION_ERROR", "The Claude connector doesn't sign people in")
    return None


def _active_grants() -> dict[int, int]:
    rows = db.session.execute(
        select(ApiToken.oauth_client_id, func.count(ApiToken.id))
        .where(
            ApiToken.oauth_client_id.is_not(None),
            ApiToken.revoked_at.is_(None),
            ApiToken.expires_at > datetime.now(timezone.utc),
        )
        .group_by(ApiToken.oauth_client_id)
    ).all()
    return {cid: int(n) for cid, n in rows}


@platform_oauth_bp.get("/apps")
@require_global_permission("platform.settings")
@api_tokens.no_api_tokens
def list_apps():
    counts = _active_grants()
    clients = db.session.scalars(
        select(OAuthClient).order_by(OAuthClient.kind.desc(), OAuthClient.created_at.desc()).limit(500)
    ).all()
    tenant_ids = {c.tenant_id for c in clients if c.tenant_id}
    clubs = (
        {t.id: t for t in db.session.scalars(select(Tenant).where(Tenant.id.in_(tenant_ids)))}
        if tenant_ids
        else {}
    )
    from hubra.core.services import platform_settings

    return jsonify(
        {
            "items": [_app_json(c, counts.get(c.id, 0), clubs) for c in clients],
            "discoveryUrl": f"{oauth.issuer()}/.well-known/openid-configuration",
            "signingKeys": oidc.keys_info(),
            "issuer": oauth.issuer(),
            "metadataUrl": f"{oauth.issuer()}/.well-known/oauth-authorization-server",
            "mcpResource": oauth.mcp_resource(),
            "dynamicAllowed": oauth.dynamic_allowed(),
            "dynamicRedirectHosts": platform_settings.get("oauth.dynamic_redirect_hosts"),
        }
    ), 200


@platform_oauth_bp.post("/apps")
@require_global_permission("platform.settings")
@api_tokens.no_api_tokens
def create_app():
    data = _body()
    fields, error = _app_fields(data, partial=False)
    if error is not None:
        return error
    confidential = data.get("confidential", True)
    if not isinstance(confidential, bool):
        return _error(400, "VALIDATION_ERROR", "confidential: true or false")
    shape = _app_shape_error(fields["resources"], fields["scopes"])
    if shape is not None:
        return shape
    client, secret = oauth.make_client(
        kind="registered",
        name=fields["name"],
        description=fields.get("description", ""),
        client_uri=fields.get("client_uri"),
        redirect_uris=fields["redirect_uris"],
        resources=fields["resources"],
        scopes=fields["scopes"],
        confidential=confidential,
        created_by_name=_name(g.system_user),
    )
    _audit_platform("oauth_app.create", client)
    db.session.commit()
    body = _app_json(client)
    if secret:
        body["clientSecret"] = secret  # shown once
    return jsonify(body), 201


def _app_or_404(app_id: int) -> OAuthClient | None:
    return db.session.get(OAuthClient, app_id)


@platform_oauth_bp.patch("/apps/<int:app_id>")
@require_global_permission("platform.settings")
@api_tokens.no_api_tokens
def edit_app(app_id: int):
    client = _app_or_404(app_id)
    if client is None:
        return _error(404, "NOT_FOUND", "App not found")
    data = _body()
    if client.kind in ("dynamic", "club") and set(data) - {"disabled"}:
        return _error(409, "SELF_REGISTERED", "This app can only be switched off or on here")
    fields, error = _app_fields(data, partial=True)
    if error is not None:
        return error
    shape = _app_shape_error(
        fields.get("resources", client.resources or []), fields.get("scopes", client.scopes or [])
    )
    if shape is not None and ("resources" in fields or "scopes" in fields):
        return shape
    for key, value in fields.items():
        setattr(client, key, value)
    if "disabled" in data:
        if not isinstance(data["disabled"], bool):
            return _error(400, "VALIDATION_ERROR", "disabled: true or false")
        client.disabled_at = datetime.now(timezone.utc) if data["disabled"] else None
    _audit_platform("oauth_app.update", client)
    db.session.commit()
    return jsonify(_app_json(client, _active_grants().get(client.id, 0))), 200


@platform_oauth_bp.post("/apps/<int:app_id>/secret")
@require_global_permission("platform.settings")
@api_tokens.no_api_tokens
def new_app_secret(app_id: int):
    client = _app_or_404(app_id)
    if client is None or client.kind != "registered":
        return _error(404, "NOT_FOUND", "App not found")
    secret = oauth.new_client_secret(client)
    _audit_platform("oauth_app.secret", client)
    db.session.commit()
    body = _app_json(client, _active_grants().get(client.id, 0))
    body["clientSecret"] = secret  # shown once
    return jsonify(body), 200


@platform_oauth_bp.delete("/apps/<int:app_id>")
@require_global_permission("platform.settings")
@api_tokens.no_api_tokens
def delete_app(app_id: int):
    """Deletes the app and every sign-in it holds."""
    client = _app_or_404(app_id)
    if client is None:
        return _error(404, "NOT_FOUND", "App not found")
    _audit_platform("oauth_app.delete", client)
    for row in db.session.scalars(select(ApiToken).where(ApiToken.oauth_client_id == client.id)):
        db.session.delete(row)
    db.session.delete(client)
    db.session.commit()
    return jsonify({"ok": True}), 200


@platform_oauth_bp.post("/keys/rotate")
@require_global_permission("platform.settings")
@api_tokens.no_api_tokens
def rotate_signing_key():
    """A new ID token signing key; the one before stays published so
    tokens signed just now still check out."""
    keys = oidc.rotate_keys()
    db.session.add(
        GlobalAuditEntry(
            actor_id=g.system_user.id,
            action="oauth.key_rotate",
            target_type="oauth_key",
            target_id=keys[0]["kid"],
            details={"kept": [k["kid"] for k in keys[1:]]},
            ip_address=(request.remote_addr or "")[:45],
        )
    )
    db.session.commit()
    return jsonify({"signingKeys": oidc.keys_info()}), 200


# ── A club's own sign-in apps (club admins) ─────────────────────────────────

MAX_CLUB_APPS = 10


def _club_admin():
    """(tenant, member) for the club admin making this request."""
    from hubra.core.permissions import _current_member
    from hubra.core.tenant.context import current_tenant

    return current_tenant(), _current_member()


def _no_support_session():
    """A sign-in app speaks for the club to its members: never made by
    someone in a support session."""
    from flask_jwt_extended import get_jwt

    if get_jwt().get("impersonator_id") is not None:
        return _error(403, "IMPERSONATION_RESTRICTED", "Not during a support session")
    return None


def _club_app(tenant, app_id: int) -> OAuthClient | None:
    client = db.session.get(OAuthClient, app_id)
    if client is None or tenant is None or client.tenant_id != tenant.id:
        return None
    return client


def _club_app_fields(data: dict, *, partial: bool):
    """Name, description, website and return addresses of a club app."""
    allowed = {"name", "description", "clientUri", "redirectUris", "disabled", "confidential"}
    unknown = set(data) - allowed
    if unknown:
        return None, _error(400, "VALIDATION_ERROR", "Unknown field")
    fields, error = _app_fields(
        {k: v for k, v in data.items() if k in {"name", "description", "clientUri", "redirectUris"}},
        partial=partial,
    )
    if error is not None:
        return None, error
    fields.pop("resources", None)
    fields.pop("scopes", None)
    return fields, None


def _audit_club_app(action: str, client: OAuthClient, member) -> None:
    from hubra.core.utils import log_audit

    log_audit(member.id, action, "oauth_client", client.id, client.name)


def _club_list_json(tenant) -> dict:
    counts = _active_grants()
    clients = db.session.scalars(
        select(OAuthClient)
        .where(OAuthClient.tenant_id == tenant.id)
        .order_by(OAuthClient.created_at.desc())
    ).all()
    return {
        "items": [_app_json(c, counts.get(c.id, 0), {tenant.id: tenant}) for c in clients],
        "issuer": oauth.issuer(),
        "discoveryUrl": f"{oauth.issuer()}/.well-known/openid-configuration",
        "max": MAX_CLUB_APPS,
    }


@club_oauth_bp.get("/apps")
@require_admin
def club_apps():
    tenant, _member = _club_admin()
    if tenant is None:
        return _error(400, "NO_CLUB", "Open a club first")
    return jsonify(_club_list_json(tenant)), 200


@club_oauth_bp.post("/apps")
@require_admin
def create_club_app():
    """A "Sign in with Hubra" app for the club's website or forum: signs in
    the club's members only, reads nothing."""
    tenant, member = _club_admin()
    if tenant is None:
        return _error(400, "NO_CLUB", "Open a club first")
    refusal = _no_support_session()
    if refusal is not None:
        return refusal
    data = _body()
    fields, error = _club_app_fields(data, partial=False)
    if error is not None:
        return error
    confidential = data.get("confidential", True)
    if not isinstance(confidential, bool):
        return _error(400, "VALIDATION_ERROR", "confidential: true or false")
    count = db.session.scalar(
        select(func.count(OAuthClient.id)).where(OAuthClient.tenant_id == tenant.id)
    )
    if int(count or 0) >= MAX_CLUB_APPS:
        return _error(409, "OAUTH_APP_LIMIT", "This club has the most apps allowed")
    client, secret = oauth.make_client(
        kind="club",
        name=fields["name"],
        description=fields.get("description", ""),
        client_uri=fields.get("client_uri"),
        redirect_uris=fields["redirect_uris"],
        resources=[],
        scopes=["openid"],
        confidential=confidential,
        created_by_name=f"{member.user.first_name} {member.user.last_name}".strip()
        if getattr(member, "user", None)
        else "",
        tenant_id=tenant.id,
    )
    _audit_club_app("oauth_app.create", client, member)
    db.session.commit()
    body = _app_json(client, 0, {tenant.id: tenant})
    if secret:
        body["clientSecret"] = secret  # shown once
    return jsonify(body), 201


@club_oauth_bp.patch("/apps/<int:app_id>")
@require_admin
def edit_club_app(app_id: int):
    tenant, member = _club_admin()
    client = _club_app(tenant, app_id)
    if client is None:
        return _error(404, "NOT_FOUND", "App not found")
    data = _body()
    if "confidential" in data:
        return _error(400, "VALIDATION_ERROR", "Make a new app to change the kind")
    fields, error = _club_app_fields(data, partial=True)
    if error is not None:
        return error
    for key, value in fields.items():
        setattr(client, key, value)
    if "disabled" in data:
        if not isinstance(data["disabled"], bool):
            return _error(400, "VALIDATION_ERROR", "disabled: true or false")
        client.disabled_at = datetime.now(timezone.utc) if data["disabled"] else None
    _audit_club_app("oauth_app.update", client, member)
    db.session.commit()
    return jsonify(_app_json(client, _active_grants().get(client.id, 0), {tenant.id: tenant})), 200


@club_oauth_bp.post("/apps/<int:app_id>/secret")
@require_admin
def new_club_app_secret(app_id: int):
    tenant, member = _club_admin()
    client = _club_app(tenant, app_id)
    if client is None or not client.secret_hash:
        return _error(404, "NOT_FOUND", "App not found")
    refusal = _no_support_session()
    if refusal is not None:
        return refusal
    secret = oauth.new_client_secret(client)
    _audit_club_app("oauth_app.secret", client, member)
    db.session.commit()
    body = _app_json(client, _active_grants().get(client.id, 0), {tenant.id: tenant})
    body["clientSecret"] = secret  # shown once
    return jsonify(body), 200


@club_oauth_bp.delete("/apps/<int:app_id>")
@require_admin
def delete_club_app(app_id: int):
    """Deletes the app and every sign-in it holds."""
    tenant, member = _club_admin()
    client = _club_app(tenant, app_id)
    if client is None:
        return _error(404, "NOT_FOUND", "App not found")
    _audit_club_app("oauth_app.delete", client, member)
    for row in db.session.scalars(select(ApiToken).where(ApiToken.oauth_client_id == client.id)):
        db.session.delete(row)
    db.session.delete(client)
    db.session.commit()
    return jsonify({"ok": True}), 200
