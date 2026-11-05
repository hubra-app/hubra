"""Sign in with Hubra (docs/oidc.md): OpenID Connect on the OAuth server.

A club admin registers the club website as an app; members sign in there
with their Hubra account; the site gets a signed ID token and userinfo,
and nothing else from Hubra."""

from __future__ import annotations

import base64
import hashlib
import json
from urllib.parse import parse_qs, urlsplit

import jwt
import pytest

from hubra.core.auth import api_tokens, oidc
from hubra.core.models.api_token import ApiToken
from hubra.core.models.oauth import OAuthClient
from hubra.core.services import platform_settings

from tests.auth.test_api_tokens import (  # noqa: F401  (fixtures)
    PASSWORD,
    _bearer,
    _login,
    _sign_in,
    _two_factor,
    catalog,
)

ISSUER = "https://api.hubra.test"
SITE = "https://www.club-a.test/oidc/callback"
VERIFIER = "w" * 64
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=").decode()
)
USERINFO = "/api/v1/global/oauth/userinfo"


@pytest.fixture(autouse=True)
def _setup(app, db, monkeypatch):
    api_tokens.reset_rate_limits()
    monkeypatch.setitem(app.config, "API_PUBLIC_URL", ISSUER)
    monkeypatch.setitem(app.config, "SSO_BASE_URL", "https://sso.hubra.test")
    with app.app_context():
        platform_settings.set_many({"mcp.url": "https://mcp.hubra.test"})
        db.session.commit()
    yield
    api_tokens.reset_rate_limits()


@pytest.fixture
def admin(app, db, tenant_pair, catalog):  # noqa: F811
    """user@test.ch, admin of tenant-a, signed in to the club and SSO."""
    c = app.test_client()
    _sign_in(c)
    _two_factor(db, tenant_pair["user"])
    return c


@pytest.fixture
def site(admin):
    resp = admin.post(
        "/api/v1/app/oauth/apps",
        json={
            "name": "Vereinswebsite",
            "clientUri": "https://www.club-a.test",
            "redirectUris": [SITE],
        },
    )
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def _params(client_id, **extra):
    return {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": SITE,
        "scope": "openid profile email club",
        "state": "s1",
        "nonce": "n-123",
        **extra,
    }


def _allow(c, client_id, **params):
    resp = c.post(
        "/api/v1/global/oauth/authorize",
        json={"params": _params(client_id, **params), "allow": True},
    )
    assert resp.status_code == 200, resp.get_json()
    url = resp.get_json()["redirect"]
    q = parse_qs(urlsplit(url).query)
    assert url.startswith(SITE)
    assert q["state"] == ["s1"]
    return q["code"][0]


def _token(client, app_json, code, **extra):
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": app_json["clientId"],
        "client_secret": app_json["clientSecret"],
        "redirect_uri": SITE,
        **extra,
    }
    return client.post("/api/v1/global/oauth/token", data=data)


def _verify(app, id_token, audience):
    with app.app_context():
        keys = {k["kid"]: k for k in oidc.jwks()["keys"]}
    kid = jwt.get_unverified_header(id_token)["kid"]
    key = jwt.PyJWK.from_dict(keys[kid])
    return jwt.decode(id_token, key.key, algorithms=["RS256"], audience=audience, issuer=ISSUER)


@pytest.fixture
def signed_in_site(app, db, admin, site):
    code = _allow(admin, site["clientId"])
    resp = _token(app.test_client(), site, code)
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()


# ── Metadata and keys ───────────────────────────────────────────────────────


def test_discovery(client):
    meta = client.get("/.well-known/openid-configuration").get_json()
    assert meta["issuer"] == ISSUER
    assert meta["jwks_uri"] == f"{ISSUER}/api/v1/global/oauth/jwks"
    assert meta["userinfo_endpoint"] == f"{ISSUER}{USERINFO}"
    assert meta["id_token_signing_alg_values_supported"] == ["RS256"]
    assert meta["subject_types_supported"] == ["pairwise"]
    assert "openid" in meta["scopes_supported"]
    assert meta["authorization_endpoint"] == "https://sso.hubra.test/oauth/authorize"


def test_jwks_and_rotation(app, db, client):
    first = client.get("/api/v1/global/oauth/jwks").get_json()["keys"]
    assert len(first) == 1 and first[0]["kty"] == "RSA" and "d" not in first[0]
    # The private part is stored encrypted, never in the clear.
    with app.app_context():
        from hubra.core.models.platform_setting import PlatformSetting

        row = db.session.get(PlatformSetting, "oauth.signing_keys")
        assert row.secret and "PRIVATE KEY" not in row.value
        oidc.rotate_keys()
        db.session.commit()
    keys = client.get("/api/v1/global/oauth/jwks").get_json()["keys"]
    assert len(keys) == 2 and keys[1]["kid"] == first[0]["kid"]


# ── A club's website ────────────────────────────────────────────────────────


def test_club_admin_registers_a_sign_in_app(admin, site):
    assert site["kind"] == "club"
    assert site["clientSecret"]
    assert site["signIn"] is True
    assert site["resources"] == [] and site["scopes"] == ["openid"]
    assert site["club"]["slug"] == "tenant-a"
    listed = admin.get("/api/v1/app/oauth/apps").get_json()
    assert [a["id"] for a in listed["items"]] == [site["id"]]
    assert listed["discoveryUrl"].endswith("/.well-known/openid-configuration")
    assert "clientSecret" not in listed["items"][0]


def test_other_club_does_not_see_it(app, admin, site):
    c = app.test_client()
    _sign_in(c, slug="tenant-b")
    assert c.get("/api/v1/app/oauth/apps").get_json()["items"] == []
    assert c.delete(f"/api/v1/app/oauth/apps/{site['id']}").status_code == 404


def test_consent_shows_sign_in_and_the_club(admin, site):
    body = admin.get(
        "/api/v1/global/oauth/authorize", query_string=_params(site["clientId"])
    ).get_json()
    assert body["mode"] == "identity"
    assert body["oidc"] == ["openid", "profile", "email", "club"]
    assert body["client"]["kind"] == "club"
    assert body["club"] == {
        "slug": "tenant-a",
        "name": "Tenant A",
        "available": True,
        "reason": None,
    }
    assert body["remembered"] is False


def test_sign_in_gives_an_id_token(app, db, site, signed_in_site, tenant_pair):
    body = signed_in_site
    assert body["access_token"].startswith("hbr_oai_")
    assert body["scope"] == "openid profile email club"
    claims = _verify(app, body["id_token"], site["clientId"])
    assert claims["nonce"] == "n-123"
    assert claims["email"] == "user@test.ch" and claims["email_verified"] is True
    assert claims["name"] == "Test User"
    assert claims["hubra_club"]["slug"] == "tenant-a"
    assert claims["hubra_club"]["admin"] is True
    assert claims["auth_time"] <= claims["iat"]
    assert len(claims["sub"]) == 32 and str(tenant_pair["user"].id) != claims["sub"]


def test_userinfo(app, client, site, signed_in_site):
    resp = client.get(USERINFO, headers=_bearer(signed_in_site["access_token"]))
    assert resp.status_code == 200, resp.get_json()
    info = resp.get_json()
    claims = _verify(app, signed_in_site["id_token"], site["clientId"])
    assert info["sub"] == claims["sub"]
    assert info["email"] == "user@test.ch"
    assert info["hubra_club"]["name"] == "Tenant A"
    # POST and a browser (Origin) work too: userinfo is for apps of any kind.
    resp = client.post(
        USERINFO,
        headers=_bearer(signed_in_site["access_token"], Origin="https://www.club-a.test"),
    )
    assert resp.status_code == 200


def test_userinfo_refuses_bad_tokens(client, signed_in_site):
    resp = client.get(USERINFO)
    assert resp.status_code == 401
    assert "Bearer" in resp.headers["WWW-Authenticate"]
    token = signed_in_site["access_token"]
    resp = client.get(USERINFO, headers=_bearer(token[:-2] + "zz"))
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "invalid_token"


def test_sign_in_token_reads_nothing(client, signed_in_site):
    resp = client.get(
        "/api/v1/app/events",
        headers=_bearer(signed_in_site["access_token"], **{"X-Tenant-Slug": "tenant-a"}),
    )
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "API_TOKEN_AUDIENCE"


def test_refresh_gives_a_new_id_token(app, client, site, signed_in_site):
    resp = client.post(
        "/api/v1/global/oauth/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": signed_in_site["refresh_token"],
            "client_id": site["clientId"],
            "client_secret": site["clientSecret"],
        },
    )
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["scope"] == "openid profile email club"
    claims = _verify(app, body["id_token"], site["clientId"])
    assert "nonce" not in claims


def test_second_sign_in_is_remembered(admin, site, signed_in_site):
    body = admin.get(
        "/api/v1/global/oauth/authorize", query_string=_params(site["clientId"])
    ).get_json()
    assert body["remembered"] is True
    # More claims than before, or prompt=consent: ask again.
    body = admin.get(
        "/api/v1/global/oauth/authorize",
        query_string=_params(site["clientId"], prompt="consent"),
    ).get_json()
    assert body["remembered"] is False


def test_prompt_none(app, admin, site, signed_in_site):
    body = admin.get(
        "/api/v1/global/oauth/authorize",
        query_string=_params(site["clientId"], prompt="none"),
    ).get_json()
    assert body["remembered"] is True and "problem" not in body
    anon = app.test_client()
    body = anon.get(
        "/api/v1/global/oauth/authorize",
        query_string=_params(site["clientId"], prompt="none"),
    ).get_json()
    q = parse_qs(urlsplit(body["problem"]["redirect"]).query)
    assert q["error"] == ["login_required"] and q["state"] == ["s1"]


def test_prompt_none_without_consent(admin, site):
    body = admin.get(
        "/api/v1/global/oauth/authorize",
        query_string=_params(site["clientId"], prompt="none"),
    ).get_json()
    q = parse_qs(urlsplit(body["problem"]["redirect"]).query)
    assert q["error"] == ["consent_required"]


def test_only_club_members_sign_in(app, db, site):
    from hubra.core.models.user import User

    outsider = User(email="out@test.ch", first_name="Out", last_name="Sider")
    outsider.set_password(PASSWORD)
    db.session.add(outsider)
    db.session.commit()
    c = app.test_client()
    _login(c, "out@test.ch")
    body = c.get(
        "/api/v1/global/oauth/authorize", query_string=_params(site["clientId"])
    ).get_json()
    assert body["club"]["available"] is False
    assert body["club"]["reason"] == "NOT_MEMBER"
    resp = c.post(
        "/api/v1/global/oauth/authorize",
        json={"params": _params(site["clientId"]), "allow": True},
    )
    assert resp.status_code == 403


def test_leaving_the_club_ends_the_sign_in(app, db, client, site, signed_in_site, tenant_pair):
    from datetime import datetime, timezone

    from hubra.core.models.member import Member

    for m in db.session.scalars(
        db.select(Member).where(Member.user_id == tenant_pair["user"].id)
    ):
        m.archived_at = datetime.now(timezone.utc)
    db.session.commit()
    resp = client.get(USERINFO, headers=_bearer(signed_in_site["access_token"]))
    assert resp.status_code == 401
    resp = client.post(
        "/api/v1/global/oauth/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": signed_in_site["refresh_token"],
            "client_id": site["clientId"],
            "client_secret": site["clientSecret"],
        },
    )
    assert resp.status_code == 400
    row = db.session.scalar(db.select(ApiToken).where(ApiToken.kind == "identity"))
    assert row.revoked_reason == "left_club"


def test_pkce_needed_without_nonce_or_secret(app, admin, site):
    # No nonce: PKCE is required.
    resp = admin.get(
        "/api/v1/global/oauth/authorize", query_string=_params(site["clientId"], nonce="")
    ).get_json()
    assert resp["problem"]["error"] == "invalid_request"
    # With PKCE it works, and the verifier must match.
    code = _allow(
        admin,
        site["clientId"],
        nonce="",
        code_challenge=CHALLENGE,
        code_challenge_method="S256",
    )
    resp = _token(app.test_client(), site, code, code_verifier="x" * 64)
    assert resp.get_json()["error"] == "invalid_grant"


def test_pkce_needed_for_an_app_without_secret(app, admin):
    resp = admin.post(
        "/api/v1/app/oauth/apps",
        json={"name": "Forum", "redirectUris": [SITE], "confidential": False},
    )
    assert resp.status_code == 201
    body = admin.get(
        "/api/v1/global/oauth/authorize", query_string=_params(resp.get_json()["clientId"])
    ).get_json()
    assert body["problem"]["error"] == "invalid_request"


def test_sign_in_app_may_not_ask_to_read(admin, site):
    body = admin.get(
        "/api/v1/global/oauth/authorize",
        query_string=_params(site["clientId"], scope="openid read"),
    ).get_json()
    assert body["problem"]["error"] == "invalid_scope"
    assert "redirect" in body["problem"]


def test_switched_off_app_ends_userinfo(app, db, admin, client, site, signed_in_site):
    resp = admin.patch(f"/api/v1/app/oauth/apps/{site['id']}", json={"disabled": True})
    assert resp.status_code == 200
    assert client.get(USERINFO, headers=_bearer(signed_in_site["access_token"])).status_code == 401


def test_club_app_limits(admin, site):
    resp = admin.patch(f"/api/v1/app/oauth/apps/{site['id']}", json={"scopes": ["read"]})
    assert resp.status_code == 400
    resp = admin.post(
        "/api/v1/app/oauth/apps",
        json={"name": "Bad", "redirectUris": ["http://evil.test/cb"]},
    )
    assert resp.status_code == 400


def test_my_apps_show_sign_ins(admin, site, signed_in_site):
    items = admin.get("/api/v1/global/oauth/grants").get_json()["items"]
    assert len(items) == 1
    assert items[0]["signIn"] is True
    assert items[0]["claims"] == ["profile", "email", "club"]
    assert items[0]["club"]["slug"] == "tenant-a"
    assert items[0]["canWrite"] is False


def test_club_admin_sees_and_deletes(app, db, admin, site, signed_in_site):
    rows = admin.get("/api/v1/app/api-tokens/").get_json()["items"]
    assert any(r["kind"] == "identity" and r["appId"] == site["id"] for r in rows)
    assert admin.delete(f"/api/v1/app/oauth/apps/{site['id']}").status_code == 200
    assert db.session.get(OAuthClient, site["id"]) is None
    assert db.session.scalar(db.select(ApiToken).where(ApiToken.kind == "identity")) is None


# ── Pairwise subject, registered apps, the connector ────────────────────────


def test_sub_differs_per_app(app, db, tenant_pair):
    with app.app_context():
        a = oidc.subject("hbr_app_a", tenant_pair["user"].id)
        b = oidc.subject("hbr_app_b", tenant_pair["user"].id)
        assert a != b and a == oidc.subject("hbr_app_a", tenant_pair["user"].id)


def _platform_admin(app, db, tenant_pair):
    tenant_pair["user"].is_superadmin = True
    db.session.commit()
    c = app.test_client()
    c.post("/api/v1/auth/login", json={"email": "user@test.ch", "password": PASSWORD})
    _two_factor(db, tenant_pair["user"])
    return c


def test_registered_sign_in_app_without_club(app, db, tenant_pair, catalog):  # noqa: F811
    c = _platform_admin(app, db, tenant_pair)
    resp = c.post(
        "/api/v1/platform/oauth/apps",
        json={"name": "Hubra Forum", "redirectUris": [SITE], "resources": [], "scopes": ["openid"]},
    )
    assert resp.status_code == 201, resp.get_json()
    forum = resp.get_json()
    assert forum["signIn"] is True and forum["club"] is None
    body = c.get(
        "/api/v1/global/oauth/authorize", query_string=_params(forum["clientId"])
    ).get_json()
    assert body["mode"] == "identity" and body["club"] is None
    # "club" is only for a club's own app.
    assert body["oidc"] == ["openid", "profile", "email"]
    code = _allow(c, forum["clientId"])
    tokens = _token(app.test_client(), forum, code).get_json()
    claims = _verify(app, tokens["id_token"], forum["clientId"])
    assert "hubra_club" not in claims
    listed = c.get("/api/v1/platform/oauth/apps").get_json()
    assert listed["signingKeys"] and listed["discoveryUrl"]


def test_app_shape_rules(app, db, tenant_pair, catalog):  # noqa: F811
    c = _platform_admin(app, db, tenant_pair)

    def make(resources, scopes):
        return c.post(
            "/api/v1/platform/oauth/apps",
            json={"name": "X", "redirectUris": [SITE], "resources": resources, "scopes": scopes},
        ).status_code

    assert make([], ["read"]) == 400
    assert make([], []) == 400
    assert make(["mcp"], ["read", "openid"]) == 400
    assert make(["api"], ["read", "openid"]) == 201


def test_api_app_can_also_sign_in(app, db, tenant_pair, catalog):  # noqa: F811
    c = _platform_admin(app, db, tenant_pair)
    made = c.post(
        "/api/v1/platform/oauth/apps",
        json={
            "name": "Club tool",
            "redirectUris": [SITE],
            "resources": ["api"],
            "scopes": ["read", "openid"],
        },
    ).get_json()
    params = _params(
        made["clientId"],
        scope="read openid email",
        code_challenge=CHALLENGE,
        code_challenge_method="S256",
        resource=ISSUER,
    )
    resp = c.post(
        "/api/v1/global/oauth/authorize",
        json={"params": params, "allow": True, "club": "tenant-a"},
    )
    assert resp.status_code == 200, resp.get_json()
    code = parse_qs(urlsplit(resp.get_json()["redirect"]).query)["code"][0]
    body = _token(app.test_client(), made, code, code_verifier=VERIFIER).get_json()
    assert body["access_token"].startswith("hbr_oam_")
    assert body["scope"] == "read openid email"
    claims = _verify(app, body["id_token"], made["clientId"])
    assert claims["email"] == "user@test.ch" and "name" not in claims


def test_connector_ignores_openid(app, db, client, tenant_pair, catalog):  # noqa: F811
    reg = client.post(
        "/api/v1/global/oauth/register",
        json={
            "client_name": "Claude",
            "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
            "token_endpoint_auth_method": "none",
        },
    ).get_json()
    tenant_pair["tenant_a"].settings = {"api_tokens": {"ai": True}}
    db.session.commit()
    c = app.test_client()
    _login(c)
    params = {
        "response_type": "code",
        "client_id": reg["client_id"],
        "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
        "code_challenge": CHALLENGE,
        "code_challenge_method": "S256",
        "state": "s1",
        "resource": "https://mcp.hubra.test/mcp",
        "scope": "read openid email",
    }
    body = c.get("/api/v1/global/oauth/authorize", query_string=params).get_json()
    assert body["mode"] == "access" and body["oidc"] == []


def test_settings_keys_are_not_listed_in_clear(app, db, client):
    client.get("/api/v1/global/oauth/jwks")
    with app.app_context():
        stored = json.loads(platform_settings.get("oauth.signing_keys"))
        assert stored[0]["pem"].startswith("-----BEGIN PRIVATE KEY-----")
