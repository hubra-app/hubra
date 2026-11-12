"""OAuth for outside apps (docs/oauth.md): consent on SSO, codes with PKCE,
hour-long access tokens, rotating refresh tokens, one resource per token,
and the same checks as API tokens once a request runs."""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest

from hubra.core.auth import api_tokens, oauth
from hubra.core.models.api_token import ApiToken
from hubra.core.models.oauth import OAuthClient, OAuthCode
from hubra.core.services import platform_settings

from tests.auth.test_api_tokens import (  # noqa: F401  (fixtures)
    PASSWORD,
    READ,
    CREATE,
    _bearer,
    _login,
    _sign_in,
    _two_factor,
    catalog,
)

MCP = "https://mcp.hubra.test"
REDIRECT = "https://claude.ai/api/mcp/auth_callback"
VERIFIER = "v" * 64
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=").decode()
)
AI = {"X-Hubra-Client": "mcp"}


@pytest.fixture(autouse=True)
def _setup(app, db, monkeypatch):
    api_tokens.reset_rate_limits()
    monkeypatch.setitem(app.config, "API_PUBLIC_URL", "https://api.hubra.test")
    monkeypatch.setitem(app.config, "SSO_BASE_URL", "https://sso.hubra.test")
    with app.app_context():
        platform_settings.set_many({"mcp.url": MCP})
        db.session.commit()
    yield
    api_tokens.reset_rate_limits()


def _register(client, **body):
    payload = {
        "client_name": "Claude",
        "redirect_uris": [REDIRECT],
        "token_endpoint_auth_method": "none",
        **body,
    }
    return client.post("/api/v1/global/oauth/register", json=payload)


@pytest.fixture
def app_client(client):
    resp = _register(client)
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def _params(client_id, **extra):
    return {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT,
        "code_challenge": CHALLENGE,
        "code_challenge_method": "S256",
        "state": "xyz",
        "resource": f"{MCP}/mcp",
        "scope": "read",
        **extra,
    }


def _ai_on(db, tenant):
    tenant.settings = {**(tenant.settings or {}), "api_tokens": {"ai": True}}
    db.session.commit()


def _consent(c, client_id, club="tenant-a", **extra):
    params = _params(client_id, **extra.pop("params", {}))
    resp = c.post(
        "/api/v1/global/oauth/authorize",
        json={"params": params, "allow": True, "club": club, **extra},
    )
    return resp


def _code_from(resp) -> str:
    assert resp.status_code == 200, resp.get_json()
    url = resp.get_json()["redirect"]
    assert url.startswith(REDIRECT)
    q = parse_qs(urlsplit(url).query)
    assert q["state"] == ["xyz"]
    assert q["iss"] == ["https://api.hubra.test"]
    return q["code"][0]


def _exchange(client, client_id, code, **extra):
    return client.post(
        "/api/v1/global/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "redirect_uri": REDIRECT,
            "code_verifier": VERIFIER,
            "resource": f"{MCP}/mcp",
            **extra,
        },
    )


@pytest.fixture
def signed_in(app, db, tenant_pair, catalog):  # noqa: F811
    _ai_on(db, tenant_pair["tenant_a"])
    c = app.test_client()
    _login(c)
    return c


@pytest.fixture
def tokens(app, db, signed_in, app_client):
    code = _code_from(_consent(signed_in, app_client["client_id"]))
    resp = _exchange(app.test_client(), app_client["client_id"], code)
    assert resp.status_code == 200, resp.get_json()
    assert resp.headers["Cache-Control"] == "no-store"
    return resp.get_json()


# ── Metadata and registration ───────────────────────────────────────────────


def test_server_metadata(client):
    meta = client.get("/.well-known/oauth-authorization-server").get_json()
    assert meta["issuer"] == "https://api.hubra.test"
    assert meta["authorization_endpoint"] == "https://sso.hubra.test/oauth/authorize"
    assert meta["token_endpoint"] == "https://api.hubra.test/api/v1/global/oauth/token"
    assert meta["code_challenge_methods_supported"] == ["S256"]
    assert meta["registration_endpoint"].endswith("/api/v1/global/oauth/register")


def test_resource_metadata(client):
    meta = client.get("/api/v1/global/oauth/resource").get_json()
    assert meta["resource"] == f"{MCP}/mcp"
    assert meta["authorization_servers"] == ["https://api.hubra.test"]


def test_registration_can_be_switched_off(app, client, db):
    platform_settings.set_many({"oauth.dynamic_clients": "off"})
    db.session.commit()
    assert _register(client).status_code == 400
    meta = client.get("/.well-known/oauth-authorization-server").get_json()
    assert "registration_endpoint" not in meta


def test_registration_only_for_allowed_return_hosts(client):
    resp = _register(client, redirect_uris=["https://evil.example/cb"])
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "invalid_redirect_uri"
    assert _register(client, redirect_uris=["http://claude.ai/cb"]).status_code == 400
    assert _register(client, redirect_uris=["http://localhost:3333/cb"]).status_code == 201


def test_registration_with_secret(client):
    body = _register(client, token_endpoint_auth_method="client_secret_post").get_json()
    assert body["client_secret"]
    assert body["token_endpoint_auth_method"] == "client_secret_post"


# ── Consent ─────────────────────────────────────────────────────────────────


def test_consent_info_lists_clubs(signed_in, app_client):
    resp = signed_in.get("/api/v1/global/oauth/authorize", query_string=_params(app_client["client_id"]))
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["client"]["name"] == "Claude"
    assert body["client"]["verified"] is False
    assert body["client"]["redirectHost"] == "claude.ai"
    assert body["resource"] == "mcp"
    clubs = {c["slug"]: c for c in body["clubs"]}
    assert clubs["tenant-a"]["available"] is True


def test_consent_needs_a_sign_in(client, app_client):
    resp = client.get("/api/v1/global/oauth/authorize", query_string=_params(app_client["client_id"]))
    assert resp.status_code == 401
    assert resp.get_json()["client"]["name"] == "Claude"


def test_unknown_redirect_is_never_followed(signed_in, app_client):
    resp = signed_in.get(
        "/api/v1/global/oauth/authorize",
        query_string=_params(app_client["client_id"], redirect_uri="https://claude.ai/other"),
    )
    problem = resp.get_json()["problem"]
    assert problem["error"] == "invalid_request" and "redirect" not in problem


def test_missing_pkce_goes_back_to_the_app(signed_in, app_client):
    resp = signed_in.get(
        "/api/v1/global/oauth/authorize",
        query_string=_params(app_client["client_id"], code_challenge_method="plain"),
    )
    assert "error=invalid_request" in resp.get_json()["problem"]["redirect"]


def test_ai_switch_off_blocks_the_club(app, db, signed_in, app_client, tenant_pair):
    tenant_pair["tenant_a"].settings = {}
    db.session.commit()
    resp = _consent(signed_in, app_client["client_id"])
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "AI_OFF"


def test_deny_goes_back_with_access_denied(signed_in, app_client):
    resp = signed_in.post(
        "/api/v1/global/oauth/authorize",
        json={"params": _params(app_client["client_id"]), "allow": False},
    )
    assert "error=access_denied" in resp.get_json()["redirect"]


def test_consent_needs_the_account_csrf_header(app, db, tenant_pair, catalog, app_client):  # noqa: F811
    _ai_on(db, tenant_pair["tenant_a"])
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(app.config, "JWT_COOKIE_CSRF_PROTECT", True)
        c = app.test_client()
        _login(c)
        resp = _consent(c, app_client["client_id"])
    assert resp.status_code == 401


def test_dynamic_apps_cannot_ask_for_write(signed_in, app_client):
    resp = _consent(signed_in, app_client["client_id"], params={"scope": "read write"})
    assert resp.get_json()["problem"]["error"] == "invalid_scope"


# ── Tokens ──────────────────────────────────────────────────────────────────


def test_token_reads_through_the_connector(app, tokens):
    assert tokens["access_token"].startswith("hbr_oam_")
    assert tokens["refresh_token"].startswith("hbr_ort_")
    assert tokens["token_type"] == "Bearer" and tokens["expires_in"] <= 3600
    c = app.test_client()
    resp = c.get("/api/v1/events/", headers=_bearer(tokens["access_token"], **AI))
    assert resp.status_code == 200, resp.get_json()
    me = c.get("/api/v1/app/api-tokens/self", headers=_bearer(tokens["access_token"], **AI))
    assert me.get_json()["app"] == {"name": "Claude", "verified": False}
    assert me.get_json()["club"]["slug"] == "tenant-a"


def test_connector_token_only_through_the_connector(app, tokens):
    c = app.test_client()
    resp = c.get("/api/v1/events/", headers=_bearer(tokens["access_token"]))
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "API_TOKEN_AUDIENCE"
    assert 'error="invalid_token"' in resp.headers["WWW-Authenticate"]


def test_scopes_are_read_only(app, tokens, db):
    row = db.session.scalar(db.select(ApiToken).where(ApiToken.oauth_client_id.is_not(None)))
    assert READ in row.scopes and CREATE not in row.scopes
    c = app.test_client()
    resp = c.post("/api/v1/events/", json={}, headers=_bearer(tokens["access_token"], **AI))
    assert resp.status_code == 403


def test_code_works_once_and_reuse_ends_the_sign_in(app, db, signed_in, app_client):
    cid = app_client["client_id"]
    code = _code_from(_consent(signed_in, cid))
    c = app.test_client()
    first = _exchange(c, cid, code).get_json()
    again = _exchange(c, cid, code)
    assert again.status_code == 400 and again.get_json()["error"] == "invalid_grant"
    resp = c.get("/api/v1/events/", headers=_bearer(first["access_token"], **AI))
    assert resp.status_code == 401


def test_code_taken_by_a_parallel_request_is_refused(app, db, signed_in, app_client):
    """Two token requests with one code: the one whose read of used_at is
    already stale loses, instead of both getting a token."""
    from werkzeug.datastructures import MultiDict

    cid = app_client["client_id"]
    code = _code_from(_consent(signed_in, cid))
    row = db.session.scalar(db.select(OAuthCode))  # this request's read
    client = db.session.get(OAuthClient, row.client_id)
    # The other request takes the code meanwhile, behind this session's back.
    db.session.execute(
        db.update(OAuthCode)
        .where(OAuthCode.id == row.id)
        .values(used_at=datetime.now(timezone.utc))
        .execution_options(synchronize_session=False)
    )
    assert row.used_at is None
    form = MultiDict(
        {
            "code": code,
            "redirect_uri": REDIRECT,
            "code_verifier": VERIFIER,
            "resource": f"{MCP}/mcp",
        }
    )
    with pytest.raises(oauth.OAuthError, match="already used"):
        oauth.exchange_code(client, form)


def test_wrong_verifier_is_refused(app, signed_in, app_client):
    cid = app_client["client_id"]
    code = _code_from(_consent(signed_in, cid))
    resp = _exchange(app.test_client(), cid, code, code_verifier="w" * 64)
    assert resp.status_code == 400 and resp.get_json()["error"] == "invalid_grant"


def test_code_expires(app, db, signed_in, app_client):
    cid = app_client["client_id"]
    code = _code_from(_consent(signed_in, cid))
    row = db.session.scalar(db.select(OAuthCode))
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.session.commit()
    assert _exchange(app.test_client(), cid, code).status_code == 400


def test_code_is_for_its_app(app, signed_in, app_client, client):
    code = _code_from(_consent(signed_in, app_client["client_id"]))
    other = _register(client).get_json()["client_id"]
    assert _exchange(app.test_client(), other, code).status_code == 400


def test_refresh_rotates(app, db, tokens, app_client):
    c = app.test_client()
    cid = app_client["client_id"]
    resp = c.post(
        "/api/v1/global/oauth/token",
        data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "client_id": cid},
    )
    assert resp.status_code == 200, resp.get_json()
    new = resp.get_json()
    assert new["refresh_token"] != tokens["refresh_token"]
    assert c.get("/api/v1/events/", headers=_bearer(new["access_token"], **AI)).status_code == 200
    # The access token before: expired, not counted as a wrong secret.
    old = c.get("/api/v1/events/", headers=_bearer(tokens["access_token"], **AI))
    assert old.status_code == 401 and old.get_json()["error"] == "API_TOKEN_EXPIRED"
    row = db.session.scalar(db.select(ApiToken).where(ApiToken.oauth_client_id.is_not(None)))
    assert row.failed_attempts == 0


def test_reused_refresh_token_ends_the_sign_in(app, db, tokens, app_client):
    c = app.test_client()
    cid = app_client["client_id"]
    data = {"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "client_id": cid}
    new = c.post("/api/v1/global/oauth/token", data=data).get_json()
    row = db.session.scalar(db.select(ApiToken).where(ApiToken.oauth_client_id.is_not(None)))
    row.refreshed_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.session.commit()
    assert c.post("/api/v1/global/oauth/token", data=data).status_code == 400
    resp = c.get("/api/v1/events/", headers=_bearer(new["access_token"], **AI))
    assert resp.status_code == 401


def test_access_token_lasts_an_hour(app, db, tokens):
    row = db.session.scalar(db.select(ApiToken).where(ApiToken.oauth_client_id.is_not(None)))
    row.access_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.session.commit()
    resp = app.test_client().get("/api/v1/events/", headers=_bearer(tokens["access_token"], **AI))
    assert resp.status_code == 401 and resp.get_json()["error"] == "API_TOKEN_EXPIRED"


def test_ai_switch_off_stops_the_token(app, db, tokens, tenant_pair):
    tenant_pair["tenant_a"].settings = {}
    db.session.commit()
    resp = app.test_client().get("/api/v1/events/", headers=_bearer(tokens["access_token"], **AI))
    assert resp.status_code == 403 and resp.get_json()["error"] == "API_TOKEN_AI_OFF"


def test_app_revokes_its_sign_in(app, tokens, app_client):
    c = app.test_client()
    resp = c.post(
        "/api/v1/global/oauth/revoke",
        data={"token": tokens["refresh_token"], "client_id": app_client["client_id"]},
    )
    assert resp.status_code == 200
    assert c.get("/api/v1/events/", headers=_bearer(tokens["access_token"], **AI)).status_code == 401


def test_secret_app_must_authenticate(app, db, signed_in, client):
    reg = _register(client, token_endpoint_auth_method="client_secret_basic").get_json()
    code = _code_from(_consent(signed_in, reg["client_id"]))
    c = app.test_client()
    assert _exchange(c, reg["client_id"], code).status_code == 401
    basic = base64.b64encode(f"{reg['client_id']}:{reg['client_secret']}".encode()).decode()
    resp = c.post(
        "/api/v1/global/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT,
            "code_verifier": VERIFIER,
        },
        headers={"Authorization": f"Basic {basic}"},
    )
    assert resp.status_code == 200, resp.get_json()


def test_signing_in_again_replaces_the_old_sign_in(app, db, signed_in, app_client, tokens):
    cid = app_client["client_id"]
    code = _code_from(_consent(signed_in, cid))
    _exchange(app.test_client(), cid, code)
    rows = db.session.scalars(db.select(ApiToken).where(ApiToken.oauth_client_id.is_not(None))).all()
    assert sorted(r.revoked_reason or "" for r in rows) == ["", "replaced"]


def test_password_reset_ends_the_sign_in(app, db, tokens, tenant_pair, app_client):
    user = tenant_pair["user"]
    user.tokens_valid_after = datetime.now(timezone.utc) + timedelta(seconds=1)
    db.session.commit()
    resp = app.test_client().post(
        "/api/v1/global/oauth/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id": app_client["client_id"],
        },
    )
    assert resp.status_code == 400


def test_switched_off_app_stops(app, db, tokens):
    client = db.session.scalar(db.select(OAuthClient))
    client.disabled_at = datetime.now(timezone.utc)
    db.session.commit()
    resp = app.test_client().get("/api/v1/events/", headers=_bearer(tokens["access_token"], **AI))
    assert resp.status_code == 401


# ── The person's apps, the club's view, manage ──────────────────────────────


def test_my_apps_list_and_end(app, signed_in, tokens):
    items = signed_in.get("/api/v1/global/oauth/grants").get_json()["items"]
    assert len(items) == 1
    assert items[0]["app"]["name"] == "Claude"
    assert items[0]["club"]["slug"] == "tenant-a"
    assert items[0]["resourceKind"] == "mcp"
    assert signed_in.delete(f"/api/v1/global/oauth/grants/{items[0]['id']}").status_code == 200
    assert signed_in.get("/api/v1/global/oauth/grants").get_json()["items"] == []
    resp = app.test_client().get("/api/v1/events/", headers=_bearer(tokens["access_token"], **AI))
    assert resp.status_code == 401


def test_club_admin_sees_and_ends_app_sign_ins(app, db, tokens):
    admin = app.test_client()
    _sign_in(admin)
    items = admin.get("/api/v1/app/api-tokens/").get_json()["items"]
    grant = next(i for i in items if i["appId"])
    assert grant["name"] == "Claude"
    # Not on "my tokens", can't be rolled or edited, only ended.
    assert admin.get("/api/v1/app/api-tokens/mine").get_json()["items"] == []
    assert admin.patch(f"/api/v1/app/api-tokens/mine/{grant['id']}", json={"name": "x"}).status_code == 409
    assert admin.delete(f"/api/v1/app/api-tokens/{grant['id']}").status_code == 200
    resp = app.test_client().get("/api/v1/events/", headers=_bearer(tokens["access_token"], **AI))
    assert resp.status_code == 401


def test_tokens_never_reach_oauth_routes(app, tokens):
    c = app.test_client()
    resp = c.get("/api/v1/global/oauth/grants", headers=_bearer(tokens["access_token"], **AI))
    assert resp.status_code == 403


@pytest.fixture
def admin(app, db, tenant_pair):
    user = tenant_pair["user"]
    user.is_superadmin = True
    db.session.commit()
    c = app.test_client()
    _login(c)
    _two_factor(db, user)
    return c


def test_manage_registers_an_app_for_the_api(app, db, admin, tenant_pair, catalog):  # noqa: F811
    resp = admin.post(
        "/api/v1/platform/oauth/apps",
        json={
            "name": "Kalender-Sync",
            "redirectUris": ["https://sync.example/cb"],
            "resources": ["api"],
            "scopes": ["read"],
        },
    )
    assert resp.status_code == 201, resp.get_json()
    reg = resp.get_json()
    assert reg["clientSecret"] and reg["kind"] == "registered"
    listed = admin.get("/api/v1/platform/oauth/apps").get_json()
    assert listed["items"][0]["clientId"] == reg["clientId"]
    assert "clientSecret" not in listed["items"][0]

    # A member (non-admin) can't hand a club to an app unless the club
    # allows personal access; the admin can.
    params = {
        "response_type": "code",
        "client_id": reg["clientId"],
        "redirect_uri": "https://sync.example/cb",
        "code_challenge": CHALLENGE,
        "code_challenge_method": "S256",
    }
    info = admin.get("/api/v1/global/oauth/authorize", query_string=params).get_json()
    assert info["resource"] == "api" and info["client"]["verified"] is True
    resp = admin.post(
        "/api/v1/global/oauth/authorize",
        json={"params": params, "allow": True, "club": "tenant-a", "days": 30},
    )
    code = parse_qs(urlsplit(resp.get_json()["redirect"]).query)["code"][0]
    resp = admin.post(
        "/api/v1/global/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": reg["clientId"],
            "client_secret": reg["clientSecret"],
            "code_verifier": VERIFIER,
        },
    )
    assert resp.status_code == 200, resp.get_json()
    access = resp.get_json()["access_token"]
    c = app.test_client()
    assert c.get("/api/v1/events/", headers=_bearer(access)).status_code == 200
    # An API token never works through the connector.
    assert c.get("/api/v1/events/", headers=_bearer(access, **AI)).status_code == 401


def test_platform_sign_in_is_read_only(app, db, admin, app_client):
    resp = admin.post(
        "/api/v1/global/oauth/authorize",
        json={"params": _params(app_client["client_id"]), "allow": True, "platform": True, "days": 30},
    )
    code = _code_from(resp)
    tokens = _exchange(app.test_client(), app_client["client_id"], code).get_json()
    assert tokens["access_token"].startswith("hbr_oap_")
    c = app.test_client()
    headers = _bearer(tokens["access_token"], **AI)
    assert c.get("/api/v1/platform/health", headers=headers).status_code == 200
    resp = c.post("/api/v1/manager/platform/mail/test", json={}, headers=headers)
    assert resp.status_code == 403


def test_platform_lifetime_is_capped(admin, app_client):
    resp = admin.post(
        "/api/v1/global/oauth/authorize",
        json={"params": _params(app_client["client_id"]), "allow": True, "platform": True, "days": 90},
    )
    assert resp.status_code == 400


def test_deleting_an_app_ends_its_sign_ins(app, db, admin, tokens):
    client_row = db.session.scalar(db.select(OAuthClient))
    assert admin.delete(f"/api/v1/platform/oauth/apps/{client_row.id}").status_code == 200
    resp = app.test_client().get("/api/v1/events/", headers=_bearer(tokens["access_token"], **AI))
    assert resp.status_code == 401


def test_loopback_redirect_any_port(app):
    with app.app_context():
        c = OAuthClient(redirect_uris=["http://127.0.0.1:1234/cb"])
        assert oauth.redirect_matches(c, "http://127.0.0.1:5555/cb")
        assert not oauth.redirect_matches(c, "http://127.0.0.1:5555/other")
        assert not oauth.redirect_matches(c, "https://127.0.0.1:5555/cb")
