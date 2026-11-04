"""API tokens: ``Authorization: Bearer hbr_…`` for scripts and integrations.

See docs/api-tokens.md for the concept. In short:

* A token always acts as a real person (a member in one club, or a platform
  admin) and passes only what that person may do right now AND what the
  token's scopes allow.
* A request with a token carries no other credential. ``ApiTokenWsgi``
  removes every cookie and the CSRF/club headers before Flask sees the
  request, and removes every ``Set-Cookie`` from the answer.
* ``authenticate`` (a before_request hook) checks the token, decides whether
  the route takes tokens at all (default deny), applies the rate limits, and
  then hands the request a short-lived JWT for that person, built here and
  never sent to the client. Everything after that (tenant resolution, the
  member lookup with its archived/blocked/two-factor checks, the RBAC
  decorators, impersonation rules) is the code the web app runs on.
* The RBAC decorators call ``club_scope_refusal`` / ``platform_scope_refusal``
  to narrow the person's rights to the token's scopes.

Routes that never take a token: everything not behind ``permission_required``,
``can_update`` or ``require_global_permission`` (account, sign-in, token
management, club switching, invites …), routes marked ``no_api_tokens``,
every ``require_step_up`` route, and plugin routes.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import re
import secrets
import string
import threading
import time
from datetime import datetime, timedelta, timezone

from flask import current_app, g, jsonify, request
from sqlalchemy import select

from hubra.core.extensions import db
from hubra.core.models.api_token import ApiToken

ENVIRON_KEY = "hubra.api_token_raw"

PREFIXES = {"member": "hbr_pat", "club": "hbr_club", "platform": "hbr_plat"}
_KIND_BY_PREFIX = {v[4:]: k for k, v in PREFIXES.items()}
_ALPHABET = string.ascii_letters + string.digits
_PUBLIC_LEN = 12
_SECRET_LEN = 43  # 43 × log2(62) ≈ 256 bits
_TOKEN_RE = re.compile(
    r"^hbr_(pat|club|plat)_([A-Za-z0-9]{%d})_([A-Za-z0-9]{%d})$"
    % (_PUBLIC_LEN, _SECRET_LEN)
)

# Lifetimes in days.
LIFETIMES = (7, 30, 90, 365)
DEFAULT_DAYS = 90
PLATFORM_MAX_DAYS = 30
UNUSED_DAYS = 60

# Per-person and per-club caps on active tokens.
MAX_PERSONAL_PER_MEMBER = 5
MAX_CLUB_PER_CLUB = 20
MAX_PLATFORM_PER_ADMIN = 5

# Wrong secrets for an existing token: this many in the window revoke it.
MAX_FAILURES = 10
FAILURE_WINDOW = timedelta(minutes=10)

# Requests per minute.
READS_PER_MINUTE = 120
WRITES_PER_MINUTE = 30
CLUB_PER_MINUTE = 600
INVALID_PER_IP_PER_MINUTE = 30

_READ_METHODS = ("GET", "HEAD")

# Blueprints that never take a token, whatever their decorators say.
_NEVER_BLUEPRINTS = frozenset(
    {
        "auth_bp",
        "account_bp",
        "linked_accounts_bp",
        "redirect_loop_bp",
        "api_tokens_bp",
        "platform_api_tokens_bp",
        "tenant_admin_bp",  # club switching, impersonation
        "plugins_bp",
        "plugin_assets_bp",
        "platform_backups_bp",
    }
)


# ── Format and hashing ───────────────────────────────────────────────────────


def _random(n: int) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


def _peppers() -> list[bytes]:
    """HMAC keys for the secret hash: from FERNET_KEY first, then the keys
    it replaced, so ``flask crypto rotate`` doesn't end every token."""
    from hubra.core import crypto

    keys: list[str] = []
    primary = current_app.config.get("FERNET_KEY")
    keys.append(primary or crypto._legacy_key().decode("ascii"))
    keys += crypto.old_keys()
    if primary:
        keys.append(crypto._legacy_key().decode("ascii"))
    return [
        hmac.new(k.encode("utf-8"), b"hubra-api-token-v1", hashlib.sha256).digest()
        for k in keys
    ]


def _hash(secret: str, pepper: bytes) -> str:
    return hmac.new(pepper, secret.encode("ascii"), hashlib.sha256).hexdigest()


def hash_secret(secret: str) -> str:
    return _hash(secret, _peppers()[0])


def _secret_matches(row: ApiToken, secret: str) -> bool:
    """Constant-time check against every pepper; re-hash with the current
    pepper when an old one matched."""
    peppers = _peppers()
    for i, pepper in enumerate(peppers):
        if hmac.compare_digest(row.secret_hash, _hash(secret, pepper)):
            if i:
                row.secret_hash = _hash(secret, peppers[0])
            return True
    return False


def parse(raw: str) -> tuple[str, str, str] | None:
    """(kind, public_id, secret) of a token string, or None."""
    m = _TOKEN_RE.match(raw or "")
    if not m:
        return None
    return _KIND_BY_PREFIX[m.group(1)], m.group(2), m.group(3)


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def is_active(row: ApiToken, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return row.revoked_at is None and _aware(row.expires_at) > now


# ── WSGI: one credential per request ────────────────────────────────────────

# Removed from a request that carries a token: no cookie session, no CSRF
# twin, no club picked by header (the token names its club).
_STRIPPED = (
    "HTTP_COOKIE",
    "HTTP_X_CSRF_TOKEN",
    "HTTP_X_ACCOUNT_CSRF",
    "HTTP_X_TENANT_SLUG",
)


class ApiTokenWsgi:
    """A request with ``Authorization: Bearer hbr_…`` keeps only the token.

    Done below Flask so nothing (flask-jwt-extended, the tenant resolver,
    a route reading a cookie) ever sees the browser credentials next to a
    token, and so no answer to a token request can set a cookie.
    """

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        auth = environ.get("HTTP_AUTHORIZATION", "")
        if not auth.startswith("Bearer hbr_"):
            return self.wsgi_app(environ, start_response)
        environ[ENVIRON_KEY] = auth[len("Bearer ") :].strip()
        for key in _STRIPPED:
            environ.pop(key, None)

        def _start(status, headers, exc_info=None):
            headers = [(k, v) for k, v in headers if k.lower() != "set-cookie"]
            return start_response(status, headers, exc_info)

        return self.wsgi_app(environ, _start)


# ── Rate limits ─────────────────────────────────────────────────────────────

_local_counts: dict[str, tuple[int, int]] = {}
_local_lock = threading.Lock()


def _hit(key: str, limit: int) -> bool:
    """Count a hit in this minute's window; True when over *limit*.

    Redis when it is there (shared by every worker); else a per-process
    counter, so a Redis outage never lifts the limit entirely.
    """
    window = int(time.time() // 60)
    full = f"apitok:rl:{key}:{window}"
    from hubra.core.redis_client import get_redis_client, mark_redis_down

    client = get_redis_client()
    if client is not None:
        try:
            pipe = client.pipeline()
            pipe.incr(full)
            pipe.expire(full, 120)
            count = int(pipe.execute()[0])
            return count > limit
        except Exception:
            mark_redis_down()
    with _local_lock:
        seen_window, count = _local_counts.get(key, (window, 0))
        if seen_window != window:
            count = 0
        count += 1
        _local_counts[key] = (window, count)
        if len(_local_counts) > 10000:
            _local_counts.clear()
    return count > limit


def reset_rate_limits() -> None:
    """Tests."""
    with _local_lock:
        _local_counts.clear()


# ── Which routes take a token ───────────────────────────────────────────────


def no_api_tokens(fn):
    """Mark a route that never takes an API token (put it under the route
    decorator; ``functools.wraps`` carries the mark outwards)."""
    fn._api_tokens_never = True
    return fn


def _route_refusal(kind: str) -> tuple[str, str] | None:
    """Why this route doesn't take a token of *kind*, or None if it does."""
    from hubra.core.roles import is_platform_path

    view = current_app.view_functions.get(request.endpoint or "")
    if view is None:
        return None  # 404 / 405 answer as usual
    if (
        getattr(view, "_api_tokens_never", False)
        or getattr(view, "_step_up", False)
        or (request.blueprint or "") in _NEVER_BLUEPRINTS
        # Plugin code: not until a plugin opts in and is reviewed for it.
        or not (getattr(view, "__module__", "") or "").startswith("hubra.")
    ):
        return "API_TOKEN_NOT_ALLOWED", "This route can't be used with an API token"
    platform_route = is_platform_path(request.path)
    if kind == "platform":
        if not platform_route or not getattr(view, "_global_perm", None):
            return "API_TOKEN_NOT_ALLOWED", "A platform token only opens platform routes"
        if request.method not in _READ_METHODS:
            return "API_TOKEN_READ_ONLY", "Platform tokens can only read"
        return None
    if platform_route or not getattr(view, "_perm_resource", None):
        return "API_TOKEN_NOT_ALLOWED", "This route can't be used with an API token"
    return None


# ── The request hook ────────────────────────────────────────────────────────


def _refuse(status: int, code: str, message: str):
    resp = jsonify({"error": code, "message": message})
    resp.status_code = status
    return resp


def _client_ip() -> str:
    return (request.remote_addr or "")[:45]


def _ip_allowed(row: ApiToken, ip: str) -> bool:
    if not row.allowed_ips:
        return True
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for net in row.allowed_ips:
        try:
            if addr in ipaddress.ip_network(str(net), strict=False):
                return True
        except ValueError:
            continue
    return False


def _invalid(message: str = "API token invalid"):
    if _hit(f"bad:{_client_ip()}", INVALID_PER_IP_PER_MINUTE):
        return _refuse(429, "RATE_LIMITED", "Too many invalid API tokens")
    return _refuse(401, "API_TOKEN_INVALID", message)


def _record_failure(row: ApiToken, now: datetime) -> None:
    started = _aware(row.failed_window_started_at)
    if started is None or now - started > FAILURE_WINDOW:
        row.failed_window_started_at = now
        row.failed_attempts = 0
    row.failed_attempts = (row.failed_attempts or 0) + 1
    if row.failed_attempts >= MAX_FAILURES and row.revoked_at is None:
        row.revoked_at = now
        row.revoked_reason = "failed_attempts"
        row.revoked_by_name = "Hubra"
    db.session.commit()


def _end(row: ApiToken, now: datetime, reason: str) -> None:
    row.revoked_at = now
    row.revoked_reason = reason
    row.revoked_by_name = "Hubra"
    db.session.commit()


def _path_slug() -> str | None:
    from hubra.core.tenant.middleware import _PATH_SLUG_KEY

    return request.environ.get(_PATH_SLUG_KEY)


def authenticate():
    """before_request: check a bearer token and let the request run as its
    person. No token: nothing happens."""
    raw = request.environ.get(ENVIRON_KEY)
    if raw is None:
        return None
    g.api_token = None
    if request.method == "OPTIONS":
        return _refuse(403, "API_TOKEN_BROWSER", "API tokens are not for browsers")
    # A web page can't use a token: browsers always send Origin on
    # cross-site requests, server-side clients don't.
    if request.headers.get("Origin"):
        return _refuse(403, "API_TOKEN_BROWSER", "API tokens are not for browsers")

    parsed = parse(raw)
    if parsed is None:
        return _invalid()
    kind, public_id, secret = parsed
    row = db.session.scalar(select(ApiToken).where(ApiToken.public_id == public_id))
    if row is None or row.kind != kind:
        return _invalid()
    now = datetime.now(timezone.utc)
    if not _secret_matches(row, secret):
        _record_failure(row, now)
        return _invalid()
    if row.revoked_at is not None:
        return _refuse(401, "API_TOKEN_REVOKED", "This API token was revoked")
    if _aware(row.expires_at) <= now:
        return _refuse(401, "API_TOKEN_EXPIRED", "This API token has expired")
    last = _aware(row.last_used_at) or _aware(row.created_at)
    if last is not None and now - last > timedelta(days=UNUSED_DAYS):
        _end(row, now, "unused")
        return _refuse(401, "API_TOKEN_REVOKED", "This API token was unused too long")
    if not _ip_allowed(row, _client_ip()):
        return _refuse(403, "API_TOKEN_IP", "Not allowed from this address")

    from hubra.core.models.user import User

    user = db.session.get(User, row.user_id)
    cutoff = _aware(user.tokens_valid_after) if user is not None else None
    if user is None or user.is_disabled or (
        cutoff is not None and _aware(row.created_at) < cutoff
    ):
        # Password reset or a disabled account ends tokens like sessions.
        _end(row, now, "account_reset")
        return _refuse(401, "API_TOKEN_REVOKED", "This API token was ended")

    tenant = None
    if kind == "platform":
        if row.tenant_id is not None or _path_slug():
            return _refuse(403, "API_TOKEN_WRONG_CLUB", "A platform token opens no club")
    else:
        from hubra.core.models.tenant import Tenant

        tenant = db.session.get(Tenant, row.tenant_id) if row.tenant_id else None
        if tenant is None or tenant.status != "active" or row.member_id is None:
            return _refuse(401, "API_TOKEN_REVOKED", "This club is not available")
        slug = _path_slug()
        if slug and slug != tenant.slug:
            return _refuse(403, "API_TOKEN_WRONG_CLUB", "This token is for another club")

    refusal = _route_refusal(kind)
    if refusal is not None:
        return _refuse(403, *refusal)

    write = request.method not in _READ_METHODS
    if _hit(
        f"tok:{row.id}:{'w' if write else 'r'}",
        WRITES_PER_MINUTE if write else READS_PER_MINUTE,
    ) or (tenant is not None and _hit(f"club:{tenant.id}", CLUB_PER_MINUTE)):
        return _refuse(429, "RATE_LIMITED", "Too many requests for this API token")

    # Last use, at most once a minute per token (one small write).
    used = _aware(row.last_used_at)
    if used is None or now - used > timedelta(minutes=1):
        row.last_used_at = now
        row.last_used_ip = _client_ip()
    row.use_count = (row.use_count or 0) + 1
    row.failed_attempts = 0
    db.session.commit()

    g.api_token = {
        "id": row.id,
        "kind": row.kind,
        "name": row.name,
        "scopes": frozenset(row.scopes or ()),
        "tenant_id": row.tenant_id,
    }
    _hand_over(row, tenant)
    return None


def _hand_over(row: ApiToken, tenant) -> None:
    """Give the rest of the request a short JWT for the token's person, in
    the place the web app's own JWT sits. It lives only in this request."""
    from flask_jwt_extended import create_access_token, decode_token

    claims: dict = {"api_token_id": row.id, "api_token_kind": row.kind}
    if row.kind == "platform":
        identity = f"user:{row.user_id}"
        claims["user_id"] = row.user_id
    else:
        identity = str(row.member_id)
        claims["user_id"] = row.user_id
        claims["tenant_slug"] = tenant.slug
    jwt_token = create_access_token(
        identity=identity, additional_claims=claims, expires_delta=timedelta(minutes=5)
    )
    name = current_app.config.get("JWT_ACCESS_COOKIE_NAME", "access_token_cookie")
    request.environ["HTTP_COOKIE"] = f"{name}={jwt_token}"
    csrf = decode_token(jwt_token).get("csrf")
    if csrf:
        header = current_app.config.get("JWT_ACCESS_CSRF_HEADER_NAME", "X-CSRF-TOKEN")
        request.environ["HTTP_" + header.upper().replace("-", "_")] = csrf
    # werkzeug caches the parsed cookies on first access.
    request.__dict__.pop("cookies", None)


def install(app) -> None:
    """Wrap the WSGI app and register the hook (before resolve_tenant)."""
    app.wsgi_app = ApiTokenWsgi(app.wsgi_app)
    app.before_request(authenticate)


# ── Narrowing to the token's scopes (called from api/permissions.py) ────────


def current() -> dict | None:
    return g.get("api_token")


def club_scope_refusal(member, perm_keys) -> tuple | None:
    """A 403 when this request runs on a token whose scopes miss every key
    in *perm_keys*, or a personal token the club doesn't allow; else None."""
    token = current()
    if token is None:
        return None
    if token["kind"] not in ("member", "club"):
        return _scope_error()
    if token["kind"] == "member" and not members_allowed(g.get("tenant")):
        from hubra.api.permissions import member_is_admin

        if not member_is_admin(member):
            return (
                jsonify(
                    {
                        "error": "API_TOKEN_DISABLED_BY_CLUB",
                        "message": "This club doesn't allow personal API tokens",
                    }
                ),
                403,
            )
    keys = {perm_keys} if isinstance(perm_keys, str) else set(perm_keys)
    if not keys & token["scopes"]:
        return _scope_error()
    return None


def platform_scope_refusal(permission_key: str) -> tuple | None:
    token = current()
    if token is None:
        return None
    if token["kind"] != "platform" or request.method not in _READ_METHODS:
        return _scope_error()
    if permission_key not in token["scopes"]:
        return _scope_error()
    return None


def _scope_error():
    return (
        jsonify(
            {
                "error": "API_TOKEN_SCOPE",
                "message": "This API token's scopes don't cover this",
            }
        ),
        403,
    )


def audit_label() -> str | None:
    """' (Token «name»)' for audit entries written through a token."""
    token = current()
    return f" (Token «{token['name']}»)" if token else None


# ── Club setting ────────────────────────────────────────────────────────────


def members_allowed(tenant) -> bool:
    """Whether members who aren't admins may hold personal tokens
    (club setting, off by default)."""
    settings = (getattr(tenant, "settings", None) or {}).get("api_tokens") or {}
    return bool(settings.get("members"))


# ── Making and ending tokens ────────────────────────────────────────────────


def make(
    *,
    kind: str,
    user,
    name: str,
    scopes: list[str],
    days: int,
    tenant=None,
    member_id: int | None = None,
    created_by_name: str = "",
    allowed_ips: list[str] | None = None,
) -> tuple[ApiToken, str]:
    """Create a token row; returns it with the one-time plaintext."""
    public_id = _random(_PUBLIC_LEN)
    secret = _random(_SECRET_LEN)
    row = ApiToken(
        public_id=public_id,
        kind=kind,
        name=name,
        user_id=user.id,
        tenant_id=tenant.id if tenant is not None else None,
        member_id=member_id,
        created_by_name=created_by_name[:255],
        secret_hash=hash_secret(secret),
        last4=secret[-4:],
        scopes=sorted(set(scopes)),
        allowed_ips=allowed_ips or None,
        expires_at=datetime.now(timezone.utc) + timedelta(days=days),
        use_count=0,
        failed_attempts=0,
    )
    db.session.add(row)
    db.session.flush()
    return row, f"{PREFIXES[kind]}_{public_id}_{secret}"


def revoke(row: ApiToken, by_name: str, reason: str = "revoked") -> None:
    if row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        row.revoked_by_name = by_name[:255]
        row.revoked_reason = reason


def to_json(row: ApiToken) -> dict:
    def iso(v):
        v = _aware(v)
        return v.isoformat() if v else None

    return {
        "id": row.id,
        "kind": row.kind,
        "name": row.name,
        "prefix": f"{PREFIXES[row.kind]}_{row.public_id}_…{row.last4}",
        "scopes": list(row.scopes or []),
        "allowedIps": list(row.allowed_ips or []),
        "createdByName": row.created_by_name,
        "memberId": row.member_id,
        "createdAt": iso(row.created_at),
        "expiresAt": iso(row.expires_at),
        "lastUsedAt": iso(row.last_used_at),
        "lastUsedIp": row.last_used_ip,
        "useCount": row.use_count or 0,
        "revokedAt": iso(row.revoked_at),
        "revokedByName": row.revoked_by_name,
        "revokedReason": row.revoked_reason,
        "active": is_active(row),
    }


def parse_allowed_ips(value) -> list[str] | None:
    """Validated CIDR list from a request body, or raise ValueError."""
    if value in (None, "", []):
        return None
    if not isinstance(value, list) or len(value) > 20:
        raise ValueError("allowedIps must be a list of up to 20 addresses")
    out = []
    for item in value:
        out.append(str(ipaddress.ip_network(str(item).strip(), strict=False)))
    return out
