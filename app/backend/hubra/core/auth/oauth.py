"""OAuth 2.1 for outside apps (docs/oauth.md).

Hubra is the authorization server: an app sends the person to the SSO
consent page (``/oauth/authorize``), the person picks the club (or the
platform) the app may read and for how long, and the app trades the code
for tokens at ``/api/v1/global/oauth/token``.

What an app ends up holding is an ``api_tokens`` row with
``oauth_client_id`` set, so everything an API token goes through applies:
the person's live rights AND the scopes, the club's switches, rate limits,
audit, ending with a password reset. On top of that:

* The access token (``hbr_oam_…`` for a club, ``hbr_oap_…`` for the
  platform) lasts an hour; the refresh token (``hbr_ort_…``) renews it and
  is replaced each time. Showing a refresh token that was already replaced
  ends the sign-in (it was copied).
* Every token is for one resource (RFC 8707): the Hubra API or the Claude
  connector. A connector token works only through the connector, which
  counts as an AI assistant for the club's switch.
* PKCE (S256) always; exact redirect URIs (any port for a loopback one,
  RFC 8252); a code works once, five minutes.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit, urlunsplit

from flask import current_app, request
from sqlalchemy import select

from hubra.core.auth import api_tokens, oidc
from hubra.core.extensions import db
from hubra.core.models.api_token import ApiToken
from hubra.core.models.oauth import OAuthClient, OAuthCode

ACCESS_TTL = timedelta(hours=1)
CODE_TTL = timedelta(minutes=5)
# A refresh token already replaced, shown again within this time, is a
# retry (two requests at once) and only refused; later it ends the sign-in.
REFRESH_RACE = timedelta(seconds=30)
CLUB_DAYS = (30, 90)
PLATFORM_DAYS = (7, 30)
DEFAULT_CLUB_DAYS = 90
DEFAULT_PLATFORM_DAYS = 30

MAX_GRANTS_PER_USER = 20
MAX_DYNAMIC_CLIENTS = 2000
# Dynamic apps nobody signed in with are removed after this.
DYNAMIC_UNUSED = timedelta(days=7)

ACCESS_PREFIX = {"member": "hbr_oam", "platform": "hbr_oap", "identity": "hbr_oai"}
REFRESH_PREFIX = "hbr_ort"
_REFRESH_RE = re.compile(r"^hbr_ort_([A-Za-z0-9]{12})_([A-Za-z0-9]{43})$")
_CLIENT_ID_LEN = 24
_SECRET_LEN = 43

SCOPES = ("read", "write")
AUTH_METHODS = ("none", "client_secret_basic", "client_secret_post")
_LOOPBACK = ("localhost", "127.0.0.1", "[::1]", "::1")


class OAuthError(Exception):
    """An OAuth error answer (RFC 6749 §5.2 / §4.1.2.1)."""

    def __init__(self, error: str, description: str, status: int = 400):
        super().__init__(description)
        self.error = error
        self.description = description
        self.status = status


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value):
    return api_tokens._aware(value)


# ── Addresses ───────────────────────────────────────────────────────────────


def issuer() -> str:
    """The authorization server's identifier: the public API origin."""
    base = current_app.config.get("API_PUBLIC_URL") or request.host_url
    return base.rstrip("/")


def sso_base() -> str:
    return (current_app.config.get("SSO_BASE_URL") or "").rstrip("/")


def mcp_resource() -> str | None:
    """The Claude connector's canonical URL (platform setting mcp.url + /mcp),
    or None while it isn't set up."""
    from hubra.core.services import platform_settings

    base = (platform_settings.get("mcp.url") or "").strip().rstrip("/")
    return f"{base}/mcp" if base else None


def api_resource() -> str:
    return issuer()


def _canonical(uri: str) -> str:
    parts = urlsplit(uri.strip())
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def resource_kind(resource: str | None) -> str | None:
    """``mcp`` or ``api`` for a token's resource, else None."""
    if not resource:
        return None
    value = _canonical(resource)
    mcp = mcp_resource()
    if mcp and value in (_canonical(mcp), _canonical(mcp[: -len("/mcp")])):
        return "mcp"
    if value == _canonical(api_resource()):
        return "api"
    return None


def resource_for(kind: str) -> str:
    return mcp_resource() if kind == "mcp" else api_resource()  # type: ignore[return-value]


# ── Settings ────────────────────────────────────────────────────────────────


def dynamic_allowed() -> bool:
    from hubra.core.services import platform_settings

    return str(platform_settings.get("oauth.dynamic_clients")).lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def dynamic_redirect_hosts() -> list[str]:
    from hubra.core.services import platform_settings

    raw = str(platform_settings.get("oauth.dynamic_redirect_hosts") or "")
    return [h.strip().lower() for h in raw.split(",") if h.strip()]


# ── Secrets ─────────────────────────────────────────────────────────────────


def _random(n: int) -> str:
    return api_tokens._random(n)


def _hash(secret: str) -> str:
    return api_tokens.hash_secret(secret)


def _matches(stored: str | None, secret: str) -> bool:
    if not stored:
        return False
    return any(
        hmac.compare_digest(stored, api_tokens._hash(secret, p))
        for p in api_tokens._peppers()
    )


# ── Redirect URIs ───────────────────────────────────────────────────────────


def _is_loopback(parts) -> bool:
    return parts.scheme == "http" and (parts.hostname or "") in _LOOPBACK


def redirect_uri_problem(uri, *, dynamic: bool) -> str | None:
    """Why an app may not register this redirect URI, or None when it may.
    (A returned message, not an exception, so callers answer with fixed
    text.)"""
    if not isinstance(uri, str) or not 8 <= len(uri) <= 1000:
        return "redirect_uris: 8 to 1000 characters each"
    parts = urlsplit(uri)
    if parts.fragment or "#" in uri:
        return "redirect_uris: no fragment"
    if parts.username or parts.password:
        return "redirect_uris: no user or password"
    if not (parts.scheme == "https" and parts.hostname) and not _is_loopback(parts):
        return "redirect_uris: https, or http on localhost"
    if dynamic:
        hosts = dynamic_redirect_hosts()
        host = (parts.hostname or "").lower()
        if hosts and not any(host == h or host.endswith("." + h) for h in hosts):
            return f"redirect_uris: {host} is not allowed for self-registered apps"
    return None


def redirect_matches(client: OAuthClient, uri: str | None) -> bool:
    """Exact match with a registered URI; a loopback one with any port."""
    if not uri:
        return False
    for registered in client.redirect_uris or []:
        if uri == registered:
            return True
        a, b = urlsplit(registered), urlsplit(uri)
        if (
            _is_loopback(a)
            and _is_loopback(b)
            and a.hostname == b.hostname
            and a.path == b.path
            and a.query == b.query
        ):
            return True
    return False


def with_params(uri: str, **params) -> str:
    sep = "&" if urlsplit(uri).query else "?"
    return uri + sep + urlencode({k: v for k, v in params.items() if v is not None})


# ── Clients ─────────────────────────────────────────────────────────────────


def find_client(client_id: str | None) -> OAuthClient | None:
    if not isinstance(client_id, str) or not 1 <= len(client_id) <= 64:
        return None
    client = db.session.scalar(
        select(OAuthClient).where(OAuthClient.client_id == client_id)
    )
    if client is None or client.disabled_at is not None:
        return None
    return client


def make_client(
    *,
    kind: str,
    name: str,
    redirect_uris: list[str],
    resources: list[str],
    scopes: list[str],
    confidential: bool,
    description: str = "",
    client_uri: str | None = None,
    created_by_name: str = "",
    tenant_id: int | None = None,
) -> tuple[OAuthClient, str | None]:
    """A new app; returns it with its secret (shown once) or None."""
    secret = _random(_SECRET_LEN) if confidential else None
    client = OAuthClient(
        client_id=f"hbr_app_{_random(_CLIENT_ID_LEN)}",
        kind=kind,
        name=name[:100],
        description=(description or "")[:500],
        client_uri=client_uri,
        redirect_uris=list(redirect_uris),
        secret_hash=_hash(secret) if secret else None,
        secret_last4=secret[-4:] if secret else None,
        resources=sorted(set(resources)),
        scopes=sorted(set(scopes)),
        created_by_name=created_by_name[:255],
        created_ip=(request.remote_addr or "")[:45] if request else None,
        tenant_id=tenant_id,
    )
    db.session.add(client)
    db.session.flush()
    return client, secret


def new_client_secret(client: OAuthClient) -> str:
    secret = _random(_SECRET_LEN)
    client.secret_hash = _hash(secret)
    client.secret_last4 = secret[-4:]
    return secret


def authenticate_client(form, headers) -> OAuthClient:
    """The app calling the token or revocation endpoint (RFC 6749 §2.3).

    A public app sends only ``client_id`` (PKCE carries the proof); an app
    with a secret must send it, by Basic auth or in the form."""
    client_id = form.get("client_id")
    secret = form.get("client_secret")
    auth = headers.get("Authorization", "")
    if auth.startswith("Basic "):
        try:
            raw = base64.b64decode(auth[6:].strip()).decode("utf-8")
            from urllib.parse import unquote

            cid, _, sec = raw.partition(":")
            client_id, secret = unquote(cid), unquote(sec)
        except Exception:
            raise OAuthError("invalid_client", "Bad Basic credentials", 401) from None
    client = find_client(client_id)
    if client is None:
        raise OAuthError("invalid_client", "Unknown app", 401)
    if client.secret_hash:
        if not secret or not _matches(client.secret_hash, secret):
            raise OAuthError("invalid_client", "Wrong app secret", 401)
    elif secret:
        raise OAuthError("invalid_client", "This app has no secret", 401)
    return client


def cleanup_dynamic() -> None:
    """Remove self-registered apps nobody signed in with for a week."""
    cutoff = _now() - DYNAMIC_UNUSED
    used = select(ApiToken.oauth_client_id).where(ApiToken.oauth_client_id.is_not(None))
    stale = db.session.scalars(
        select(OAuthClient).where(
            OAuthClient.kind == "dynamic",
            OAuthClient.created_at < cutoff,
            OAuthClient.id.not_in(used),
        ).limit(200)
    ).all()
    for client in stale:
        db.session.delete(client)
    db.session.execute(
        OAuthCode.__table__.delete().where(OAuthCode.expires_at < _now() - CODE_TTL)
    )


# ── The authorization request ───────────────────────────────────────────────


def parse_scope(raw: str | None, client: OAuthClient) -> list[str]:
    """The requested API scopes: ``read`` (default) and/or ``write``, or
    none for an app that only signs people in. Unknown values (an MCP
    scope) are ignored; asking for more than the app may have is an error."""
    if not client.resources:
        if {s for s in (raw or "").split()} & set(SCOPES):
            raise OAuthError("invalid_scope", "This app only signs people in")
        return []
    asked = {s for s in (raw or "").split() if s in SCOPES} or {"read"}
    if not asked <= set(client.scopes or ("read",)):
        raise OAuthError("invalid_scope", "This app may not ask for that")
    return sorted(asked)


def parse_oidc_scope(raw: str | None, client: OAuthClient) -> list[str]:
    """The OpenID Connect scopes (docs/oidc.md), only for an app that may
    sign people in: ``openid`` and with it ``profile``, ``email`` and, for a
    club's own app, ``club``. Others ignore them."""
    from hubra.core.auth.oidc import OIDC_SCOPES

    asked = {s for s in (raw or "").split() if s in OIDC_SCOPES}
    if "openid" not in (client.scopes or []) or "openid" not in asked:
        return []
    if client.tenant_id is None:
        asked.discard("club")
    order = {name: i for i, name in enumerate(OIDC_SCOPES)}
    return sorted(asked, key=order.__getitem__)


def check_request(args) -> dict:
    """Validate an authorization request (query of /oauth/authorize).

    Returns ``{client, redirect_uri, state, code_challenge, resource,
    resource_kind, scopes}``. Raises OAuthError; ``redirectable`` on it says
    whether the error may be sent back to the app (only once the client and
    its redirect URI are known good)."""
    client = find_client(args.get("client_id"))
    if client is None:
        err = OAuthError("invalid_client", "Unknown or switched-off app")
        err.redirectable = False  # type: ignore[attr-defined]
        raise err
    redirect_uri = args.get("redirect_uri")
    if not redirect_uri and len(client.redirect_uris or []) == 1:
        redirect_uri = client.redirect_uris[0]
    if not redirect_matches(client, redirect_uri):
        err = OAuthError("invalid_request", "This return address isn't registered for the app")
        err.redirectable = False  # type: ignore[attr-defined]
        raise err

    def bad(error: str, description: str):
        err = OAuthError(error, description)
        err.redirectable = True  # type: ignore[attr-defined]
        err.redirect_uri = redirect_uri  # type: ignore[attr-defined]
        err.state = args.get("state")  # type: ignore[attr-defined]
        return err

    if args.get("response_type") != "code":
        raise bad("unsupported_response_type", "Only response_type=code")
    state = args.get("state")
    if state is not None and len(state) > 500:
        raise bad("invalid_request", "state: at most 500 characters")
    oidc_scopes = parse_oidc_scope(args.get("scope"), client)
    nonce = args.get("nonce") or None
    if nonce is not None and len(nonce) > 255:
        raise bad("invalid_request", "nonce: at most 255 characters")
    prompt = set((args.get("prompt") or "").split())
    if not prompt <= {"none", "consent", "login", "select_account"} or (
        "none" in prompt and len(prompt) > 1
    ):
        raise bad("invalid_request", "prompt: none, or consent")
    if not client.resources and not oidc_scopes:
        raise bad("invalid_scope", "This app signs people in: ask for openid")
    challenge = args.get("code_challenge") or ""
    method = args.get("code_challenge_method")
    # OAuth 2.1 §7.5.1: a confidential app's OpenID sign-in with a nonce may
    # leave out PKCE (many website plugins do); everyone else uses it.
    pkce_optional = bool(client.secret_hash) and "openid" in oidc_scopes and nonce
    if challenge or method or not pkce_optional:
        if method != "S256" or not re.fullmatch(r"[A-Za-z0-9_\-]{43,128}", challenge):
            raise bad("invalid_request", "PKCE with code_challenge_method=S256 is required")

    resource = args.get("resource")
    tenant = None
    if client.tenant_id is not None:
        from hubra.core.models.tenant import Tenant

        tenant = db.session.get(Tenant, client.tenant_id)
        if tenant is None or tenant.status != "active":
            raise bad("invalid_client", "This club's app is not available")
    if not client.resources:
        # Sign-in only: the app reads nothing, so it names no resource.
        if resource:
            raise bad("invalid_target", "This app only signs people in")
        try:
            parse_scope(args.get("scope"), client)
        except OAuthError as exc:
            raise bad(exc.error, exc.description) from None
        return {
            "client": client,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": challenge,
            "resource": "",
            "resource_kind": None,
            "scopes": [],
            "oidc": oidc_scopes,
            "nonce": nonce,
            "prompt": sorted(prompt),
            "mode": "identity",
            "tenant": tenant,
        }
    if resource:
        kind = resource_kind(resource)
        if kind is None:
            raise bad("invalid_target", "Unknown resource")
    else:
        # Old clients without RFC 8707: the app's only resource, else the API.
        res = client.resources or ["api"]
        kind = res[0] if len(res) == 1 else "api"
        if kind == "mcp" and mcp_resource() is None:
            raise bad("invalid_target", "The Claude connector isn't set up")
    if kind not in (client.resources or []):
        raise bad("invalid_target", "This app may not ask for that resource")
    try:
        scopes = parse_scope(args.get("scope"), client)
    except OAuthError as exc:
        raise bad(exc.error, exc.description) from None
    if kind == "mcp" and "write" in scopes:
        raise bad("invalid_scope", "The Claude connector only reads")
    return {
        "client": client,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": challenge,
        "resource": resource_for(kind),
        "resource_kind": kind,
        "scopes": scopes,
        "oidc": oidc_scopes,
        "nonce": nonce,
        "prompt": sorted(prompt),
        "mode": "access",
        "tenant": tenant,
    }


def _club_catalog() -> list[str]:
    from hubra.core.models.role import Permission

    return list(db.session.scalars(select(Permission.key)).all())


def club_scope_keys(oauth_scopes: list[str]) -> list[str]:
    """Permission keys for a club sign-in: every read key (``read``) or every
    key (``write``). The person's live rights still cap them."""
    keys = _club_catalog()
    if "write" in oauth_scopes:
        return sorted(keys)
    return sorted(k for k in keys if _is_read(k))


def _is_read(key: str) -> bool:
    action = key.rsplit(".", 1)[-1]
    return action == "read" or action.startswith("read_")


def make_code(
    req: dict,
    *,
    user,
    kind: str,
    tenant=None,
    member_id: int | None,
    scopes: list[str],
    days: int,
    created_by_name: str,
    auth_time: datetime | None = None,
) -> str:
    code = _random(_SECRET_LEN)
    db.session.add(
        OAuthCode(
            code_hash=_hash(code),
            client_id=req["client"].id,
            user_id=user.id,
            kind=kind,
            tenant_id=tenant.id if tenant is not None else None,
            member_id=member_id,
            scopes=sorted(set(scopes)),
            oauth_scope=" ".join([*req["scopes"], *req.get("oidc", [])]),
            resource=req["resource"],
            redirect_uri=req["redirect_uri"],
            code_challenge=req["code_challenge"],
            nonce=req.get("nonce"),
            auth_time=auth_time,
            days=days,
            created_by_name=created_by_name[:255],
            expires_at=_now() + CODE_TTL,
        )
    )
    return code


def _club_of(client: OAuthClient):
    """The club a club's own app belongs to, or None."""
    if client.tenant_id is None:
        return None
    from hubra.core.models.tenant import Tenant

    return db.session.get(Tenant, client.tenant_id)


# ── Tokens ──────────────────────────────────────────────────────────────────


def _pkce_ok(verifier: str | None, challenge: str) -> bool:
    if not verifier or not re.fullmatch(r"[A-Za-z0-9\-._~]{43,128}", verifier):
        return False
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return hmac.compare_digest(expected, challenge)


def _issue(row: ApiToken) -> dict:
    """New access and refresh token for *row* (the ones before end)."""
    access = _random(api_tokens._SECRET_LEN)
    refresh = _random(api_tokens._SECRET_LEN)
    now = _now()
    row.prev_secret_hash = row.secret_hash if row.refresh_hash else None
    row.secret_hash = _hash(access)
    row.last4 = access[-4:]
    row.access_expires_at = min(now + ACCESS_TTL, _aware(row.expires_at))
    row.prev_refresh_hash = row.refresh_hash
    row.refresh_hash = _hash(refresh)
    row.refreshed_at = now
    expires_in = int((_aware(row.access_expires_at) - now).total_seconds())
    return {
        "access_token": f"{ACCESS_PREFIX[row.kind]}_{row.public_id}_{access}",
        "token_type": "Bearer",
        "expires_in": max(1, expires_in),
        "refresh_token": f"{REFRESH_PREFIX}_{row.public_id}_{refresh}",
    }


def exchange_code(client: OAuthClient, form) -> dict:
    code = form.get("code") or ""
    row = None
    if 20 <= len(code) <= 100:
        row = db.session.scalar(select(OAuthCode).where(OAuthCode.code_hash == _hash(code)))
    if row is None or row.client_id != client.id:
        raise OAuthError("invalid_grant", "Unknown code")
    now = _now()
    if row.used_at is not None:
        # A code shown twice was copied: end what it made (RFC 6749 §4.1.2).
        if row.token_id:
            token = db.session.get(ApiToken, row.token_id)
            if token is not None:
                api_tokens.revoke(token, "Hubra", reason="code_reused")
        db.session.commit()
        raise OAuthError("invalid_grant", "This code was already used")
    if _aware(row.expires_at) <= now:
        raise OAuthError("invalid_grant", "This code has expired")
    if form.get("redirect_uri") and form.get("redirect_uri") != row.redirect_uri:
        raise OAuthError("invalid_grant", "redirect_uri doesn't match")
    if row.code_challenge:
        if not _pkce_ok(form.get("code_verifier"), row.code_challenge):
            raise OAuthError("invalid_grant", "code_verifier doesn't match")
    elif not client.secret_hash:
        # Only a confidential app (it just proved its secret) skips PKCE.
        raise OAuthError("invalid_grant", "code_verifier doesn't match")
    resource = form.get("resource")
    if resource and _canonical(resource) != _canonical(row.resource):
        raise OAuthError("invalid_target", "Not the resource the person agreed to")
    row.used_at = now

    from hubra.core.models.user import User

    user = db.session.get(User, row.user_id)
    if user is None or user.is_disabled:
        raise OAuthError("invalid_grant", "This account can't sign in")
    tenant = _club_of(client)
    if client.tenant_id is not None and (
        tenant is None or oidc.club_member(tenant, user.id) is None
    ):
        raise OAuthError("invalid_grant", "Not a member of this club")

    # One sign-in per app, person and club: signing in again replaces it.
    for old in db.session.scalars(
        select(ApiToken).where(
            ApiToken.oauth_client_id == client.id,
            ApiToken.user_id == row.user_id,
            ApiToken.kind == row.kind,
            ApiToken.tenant_id.is_(None)
            if row.tenant_id is None
            else ApiToken.tenant_id == row.tenant_id,
            ApiToken.revoked_at.is_(None),
        )
    ):
        api_tokens.revoke(old, row.created_by_name, reason="replaced")

    token = ApiToken(
        public_id=_random(api_tokens._PUBLIC_LEN),
        kind=row.kind,
        name=client.name,
        user_id=row.user_id,
        tenant_id=row.tenant_id,
        member_id=row.member_id,
        created_by_name=row.created_by_name,
        secret_hash="",
        last4="",
        scopes=list(row.scopes or []),
        expires_at=now + timedelta(days=row.days),
        use_count=0,
        failed_attempts=0,
        oauth_client_id=client.id,
        resource=row.resource or None,
        oauth_scope=row.oauth_scope,
    )
    db.session.add(token)
    db.session.flush()
    row.token_id = token.id
    body = _issue(token)
    body["scope"] = row.oauth_scope
    if "openid" in row.oauth_scope.split():
        body["id_token"] = oidc.id_token(
            client=client,
            user=user,
            scopes=row.oauth_scope.split(),
            access_token=body["access_token"],
            nonce=row.nonce,
            auth_time=row.auth_time,
            tenant=tenant,
        )
    client.last_used_at = now
    _audit(token, "oauth.grant")
    db.session.commit()
    return body


def refresh(client: OAuthClient, form) -> dict:
    m = _REFRESH_RE.match(form.get("refresh_token") or "")
    if not m:
        raise OAuthError("invalid_grant", "Unknown refresh token")
    row = db.session.scalar(select(ApiToken).where(ApiToken.public_id == m.group(1)))
    if row is None or row.oauth_client_id != client.id:
        raise OAuthError("invalid_grant", "Unknown refresh token")
    secret = m.group(2)
    now = _now()
    if not _matches(row.refresh_hash, secret):
        if _matches(row.prev_refresh_hash, secret):
            rotated = _aware(row.refreshed_at)
            if rotated is None or now - rotated > REFRESH_RACE:
                # Replaced long ago and shown again: someone has a copy.
                api_tokens.revoke(row, "Hubra", reason="refresh_reused")
                db.session.commit()
            raise OAuthError("invalid_grant", "This refresh token was already used")
        raise OAuthError("invalid_grant", "Unknown refresh token")
    if row.revoked_at is not None:
        raise OAuthError("invalid_grant", "This sign-in was ended")
    if _aware(row.expires_at) <= now:
        raise OAuthError("invalid_grant", "This sign-in has expired")
    resource = form.get("resource")
    if resource and _canonical(resource) != _canonical(row.resource or ""):
        raise OAuthError("invalid_target", "Not the resource the person agreed to")
    from hubra.core.models.user import User

    user = db.session.get(User, row.user_id)
    cutoff = _aware(user.tokens_valid_after) if user is not None else None
    if user is None or user.is_disabled or (
        cutoff is not None and _aware(row.created_at) < cutoff
    ):
        api_tokens.revoke(row, "Hubra", reason="account_reset")
        db.session.commit()
        raise OAuthError("invalid_grant", "This sign-in was ended")
    tenant = _club_of(client)
    if client.tenant_id is not None and (
        tenant is None or oidc.club_member(tenant, user.id) is None
    ):
        api_tokens.revoke(row, "Hubra", reason="left_club")
        db.session.commit()
        raise OAuthError("invalid_grant", "This sign-in was ended")
    body = _issue(row)
    if row.oauth_scope is not None:
        body["scope"] = row.oauth_scope
    else:
        writes = row.kind != "platform" and any(not _is_read(k) for k in row.scopes or [])
        body["scope"] = "read write" if writes else "read"
    if "openid" in (row.oauth_scope or "").split():
        body["id_token"] = oidc.id_token(
            client=client,
            user=user,
            scopes=row.oauth_scope.split(),
            access_token=body["access_token"],
            tenant=tenant,
        )
    row.last_used_at = now
    client.last_used_at = now
    db.session.commit()
    return body


def revoke_token(client: OAuthClient, raw: str) -> None:
    """RFC 7009: end the sign-in an access or refresh token belongs to."""
    m = _REFRESH_RE.match(raw or "")
    public_id, secret, field = None, None, None
    if m:
        public_id, secret, field = m.group(1), m.group(2), "refresh"
    else:
        parsed = api_tokens.parse(raw or "")
        if parsed is not None and (raw or "").startswith("hbr_oa"):
            public_id, secret, field = parsed[1], parsed[2], "access"
    if public_id is None:
        return
    row = db.session.scalar(select(ApiToken).where(ApiToken.public_id == public_id))
    if row is None or row.oauth_client_id != client.id:
        return
    stored = row.refresh_hash if field == "refresh" else row.secret_hash
    if _matches(stored, secret):
        api_tokens.revoke(row, client.name, reason="app_revoked")
        _audit(row, "oauth.revoke")
        db.session.commit()


def end_grant(row: ApiToken, by_name: str) -> None:
    api_tokens.revoke(row, by_name, reason="revoked")
    _audit(row, "oauth.revoke")


def _audit(row: ApiToken, action: str) -> None:
    from hubra.core.models.tenant import GlobalAuditEntry

    db.session.add(
        GlobalAuditEntry(
            actor_id=row.user_id,
            action=action,
            target_type="api_token",
            target_id=str(row.id),
            details={
                "app": row.name,
                "kind": row.kind,
                "tenant_id": row.tenant_id,
                "resource": row.resource,
            },
            ip_address=(request.remote_addr or "")[:45] if request else None,
        )
    )


# ── Metadata ────────────────────────────────────────────────────────────────


def server_metadata() -> dict:
    """RFC 8414 authorization server metadata."""
    base = issuer()
    sso = sso_base() or base
    meta = {
        "issuer": base,
        "authorization_endpoint": f"{sso}/oauth/authorize",
        "token_endpoint": f"{base}/api/v1/global/oauth/token",
        "revocation_endpoint": f"{base}/api/v1/global/oauth/revoke",
        "response_types_supported": ["code"],
        "response_modes_supported": ["query"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": list(AUTH_METHODS),
        "revocation_endpoint_auth_methods_supported": list(AUTH_METHODS),
        "scopes_supported": [*SCOPES, "openid", "profile", "email", "club"],
        "authorization_response_iss_parameter_supported": True,
        "service_documentation": "https://github.com/hubra-app/hubra/blob/main/docs/oauth.md",
    }
    if dynamic_allowed() and mcp_resource():
        meta["registration_endpoint"] = f"{base}/api/v1/global/oauth/register"
    meta["userinfo_endpoint"] = f"{base}/api/v1/global/oauth/userinfo"
    meta["jwks_uri"] = f"{base}/api/v1/global/oauth/jwks"
    return meta


def resource_metadata() -> dict | None:
    """RFC 9728 metadata for the Claude connector, or None if not set up."""
    resource = mcp_resource()
    if resource is None:
        return None
    return {
        "resource": resource,
        "authorization_servers": [issuer()],
        "scopes_supported": ["read"],
        "bearer_methods_supported": ["header"],
        "resource_name": "Hubra",
        "resource_documentation": "https://github.com/hubra-app/hubra/blob/main/docs/mcp.md",
    }
