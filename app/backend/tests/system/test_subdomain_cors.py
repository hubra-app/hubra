"""Tests for the api.vollbuild.ch subdomain split (cross-origin auth).

Covers the acceptance criteria from the subdomain migration:
  - Preflight OPTIONS returns 200 with CORS headers and is not blocked by
    auth or rate limiting.
  - Exactly one Access-Control-Allow-Origin (the calling origin, from the
    allowlist), Allow-Credentials: true, and Vary: Origin. No wildcard.
  - A request from an origin NOT in the allowlist is refused CORS headers.
  - State-changing requests without the CSRF header are rejected.
  - Auth cookies are Secure / HttpOnly / Domain / SameSite=Lax (when configured).
  - Logout clears the cookie.
  - Email links point at FRONTEND_BASE_URL (the SPA), not the API host.
"""

from unittest.mock import patch

from hubra.api.health.cache import HealthCache

_ALLOWED_ORIGIN = "http://localhost:5173"  # present in TestingConfig CORS_ORIGINS


def _set_cookie_value(resp, name: str) -> str | None:
    """Extract a cookie's value from the Set-Cookie response headers."""
    for header in resp.headers.getlist("Set-Cookie"):
        if header.startswith(f"{name}="):
            return header.split(";", 1)[0].split("=", 1)[1]
    return None


def _cookie_attrs(resp, name: str) -> dict[str, str]:
    """Parse one Set-Cookie header for *name* into {attr: value} (lowercased keys).

    Per RFC 6265 the leading dot in Domain is obsolete and stripped by Werkzeug,
    so callers should compare case/leading-dot insensitively (see _domain_is).
    """
    for header in resp.headers.getlist("Set-Cookie"):
        if not header.startswith(f"{name}="):
            continue
        parts = header.split(";")
        attrs: dict[str, str] = {}
        for part in parts[1:]:
            kv = part.strip().split("=", 1)
            key = kv[0].lower()
            attrs[key] = kv[1] if len(kv) > 1 else ""
        return attrs
    return {}


def _domain_is(attrs: dict[str, str], expected: str) -> bool:
    """True if the cookie's Domain attribute matches *expected* ignoring leading dot."""
    d = attrs.get("domain", "").lstrip(".").lower()
    return d == expected.lstrip(".").lower()


# ── Preflight ──────────────────────────────────────────────────────────────────


def test_preflight_options_returns_cors_headers(client):
    """OPTIONS preflight returns 200 with CORS headers and is not 401/429."""
    HealthCache.set({"status": "ok", "services": {}, "checked_at": 0})
    resp = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": _ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type, x-csrf-token",
        },
    )
    assert resp.status_code in (200, 204)
    assert resp.headers.get("Access-Control-Allow-Origin") == _ALLOWED_ORIGIN
    assert resp.headers.get("Access-Control-Allow-Credentials") == "true"
    assert "Origin" in [v.strip() for v in resp.headers.get("Vary", "").split(",")]


def test_preflight_options_not_blocked_by_rate_limiter(app, client, seeded_db):
    """OPTIONS on a rate-limited endpoint is exempt from flask-limiter."""
    HealthCache.set({"status": "ok", "services": {}, "checked_at": 0})
    # Enable rate limiting on the shared app for this test only.
    with patch.dict(app.config, {"RATELIMIT_ENABLED": True}):
        # /api/v1/auth/login is limited to 5 per minute; fire 10 OPTIONS.
        for _ in range(10):
            resp = client.options(
                "/api/v1/auth/login",
                headers={
                    "Origin": _ALLOWED_ORIGIN,
                    "Access-Control-Request-Method": "POST",
                },
            )
            assert resp.status_code in (200, 204)
            assert resp.status_code != 429


# ── Origin allowlist ───────────────────────────────────────────────────────────


def test_allowed_origin_gets_reflected_acao_and_vary(client):
    """An allowed origin is reflected in ACAO with Allow-Credentials + Vary."""
    HealthCache.set({"status": "ok", "services": {}, "checked_at": 0})
    resp = client.get("/api/v1/health", headers={"Origin": _ALLOWED_ORIGIN})
    assert resp.status_code == 200
    assert resp.headers.get("Access-Control-Allow-Origin") == _ALLOWED_ORIGIN
    assert resp.headers.get("Access-Control-Allow-Credentials") == "true"
    assert "Origin" in [v.strip() for v in resp.headers.get("Vary", "").split(",")]
    # No duplicate ACAO header (single source of truth).
    assert len(resp.headers.getlist("Access-Control-Allow-Origin")) == 1


def test_disallowed_origin_gets_no_cors_headers(client):
    """An origin not in the allowlist receives no Access-Control-Allow-Origin."""
    HealthCache.set({"status": "ok", "services": {}, "checked_at": 0})
    resp = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})
    assert resp.status_code == 200  # endpoint is public; just no CORS headers
    assert resp.headers.get("Access-Control-Allow-Origin") is None
    assert resp.headers.get("Access-Control-Allow-Credentials") is None


def test_error_response_has_cors_headers(client):
    """CORS headers are present on error responses (401), not just 200s.

    Regression test: flask-cors must run before other after_request handlers
    so that a failure in logging/security-headers doesn't strip CORS headers
    from error responses. Without CORS headers on a 401, the browser blocks
    the response entirely and the SPA can't read the error.
    """
    HealthCache.set({"status": "ok", "services": {}, "checked_at": 0})
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@test.ch", "password": "wrong"},
        headers={"Origin": _ALLOWED_ORIGIN},
    )
    assert resp.status_code == 401
    assert resp.headers.get("Access-Control-Allow-Origin") == _ALLOWED_ORIGIN
    assert resp.headers.get("Access-Control-Allow-Credentials") == "true"
    assert "Origin" in [v.strip() for v in resp.headers.get("Vary", "").split(",")]


# ── Cookie attributes ──────────────────────────────────────────────────────────


def test_auth_cookies_have_production_attrs(app, client, seeded_db):
    """With Secure/Domain/SameSite configured, login cookies carry those attrs."""
    with patch.dict(
        app.config,
        {
            "JWT_COOKIE_SECURE": True,
            "JWT_COOKIE_DOMAIN": ".vollbuild.ch",
            "JWT_COOKIE_SAMESITE": "Lax",
        },
    ):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.ch", "password": "password123"},
        )
    assert resp.status_code == 200
    attrs = _cookie_attrs(resp, "access_token_cookie")
    assert attrs, "access_token cookie must be set on login"
    assert attrs.get("secure") == ""  # Secure is a flag (present, empty value)
    assert "httponly" in attrs
    assert _domain_is(attrs, ".vollbuild.ch")
    assert attrs.get("samesite") == "Lax"


def test_remembered_email_cookie_is_cross_subdomain_readable(app, client, seeded_db):
    """remembered_email is Domain=.vollbuild.ch + HttpOnly=False (JS-readable)."""
    with patch.dict(
        app.config,
        {
            "JWT_COOKIE_SECURE": True,
            "JWT_COOKIE_DOMAIN": ".vollbuild.ch",
        },
    ):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.ch", "password": "password123"},
        )
    email_cookies = [
        c
        for c in resp.headers.getlist("Set-Cookie")
        if c.startswith("remembered_email=")
    ]
    assert len(email_cookies) == 1
    attrs = _cookie_attrs(resp, "remembered_email")
    assert attrs.get("max-age") == "2592000"
    assert attrs.get("samesite") == "Lax"
    assert "secure" in attrs
    assert _domain_is(attrs, ".vollbuild.ch")
    # HttpOnly must NOT be present — the frontend SPA reads this via document.cookie.
    assert "httponly" not in attrs


def test_logout_clears_remembered_email_with_matching_domain(app):
    """The clear helper deletes remembered_email using the configured domain.

    The full logout flow (domain=None) is covered by test_login.py; this isolates
    the cross-subdomain delete path, which can't be exercised via the authenticated
    logout endpoint with Domain=.vollbuild.ch (the access cookie wouldn't be sent
    to the test client's localhost host).
    """
    from flask import make_response

    from hubra.api.auth.routes import _clear_remembered_email_cookie

    with patch.dict(app.config, {"JWT_COOKIE_DOMAIN": ".vollbuild.ch"}):
        with app.test_request_context("/"):
            resp = make_response("", 204)
            _clear_remembered_email_cookie(resp)
    cookies = [
        c
        for c in resp.headers.getlist("Set-Cookie")
        if c.startswith("remembered_email=")
    ]
    assert len(cookies) == 1
    assert ("Max-Age=0" in cookies[0]) or ("delete" in cookies[0].lower())
    attrs = _cookie_attrs(resp, "remembered_email")
    assert _domain_is(attrs, ".vollbuild.ch")


# ── CSRF double-submit ─────────────────────────────────────────────────────────


def test_state_changing_request_without_csrf_is_rejected(app, client, seeded_db):
    """POST to a jwt_required endpoint without X-CSRF-TOKEN is rejected."""
    with patch.dict(app.config, {"JWT_COOKIE_CSRF_PROTECT": True}):
        client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.ch", "password": "password123"},
        )
        # Logout is a jwt_required POST -> requires CSRF header.
        resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 401


def test_state_changing_request_with_csrf_succeeds(app, client, seeded_db):
    """POST to a jwt_required endpoint WITH X-CSRF-TOKEN is accepted."""
    with patch.dict(app.config, {"JWT_COOKIE_CSRF_PROTECT": True}):
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.ch", "password": "password123"},
        )
        csrf = _set_cookie_value(login, "csrf_access_token")
        assert csrf, "csrf_access_token cookie must be set when CSRF protect is on"
        resp = client.post("/api/v1/auth/logout", headers={"X-CSRF-TOKEN": csrf})
    assert resp.status_code == 204


# ── Email link generation ──────────────────────────────────────────────────────


def test_password_reset_link_uses_frontend_base_url(
    app, client, seeded_db, monkeypatch
):
    """forgot-password links point at FRONTEND_BASE_URL, not the API host."""
    monkeypatch.setitem(app.config, "FRONTEND_BASE_URL", "https://cos.vollbuild.ch")
    captured: dict = {}

    def _capture(to_email, to_name, url, lang="de-CH"):
        captured["url"] = url

    with patch(
        "hubra.api.auth.routes.email_svc.send_password_reset", side_effect=_capture
    ):
        resp = client.post(
            "/api/v1/auth/forgot-password", json={"email": "admin@test.ch"}
        )
    assert resp.status_code == 200
    assert captured["url"].startswith("https://cos.vollbuild.ch/reset-password#token=")
    assert "api.vollbuild.ch" not in captured["url"]
