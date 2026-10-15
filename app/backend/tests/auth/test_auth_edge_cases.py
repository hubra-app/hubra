"""Auth edge-case security tests — password strength, must_change_password, cookie attrs.

Covers issue #131 — Security Tests for Authentication, remaining sections:
- Weak password rejected on reset/change
- must_change_password enforcement on protected routes
- Cookie attributes in production mode (Secure, SameSite, HttpOnly)
- Referrer-Policy header present
"""

from __future__ import annotations

from unittest.mock import patch

from vollbuild.api.health.cache import HealthCache


# ── Weak password rejected on reset ───────────────────────────────────────────


def test_weak_password_rejected_on_reset(client, seeded_db):
    """reset-password rejects a weak password (zxcvbn score < 3 or < 12 chars)."""
    # First create a valid reset token
    from vollbuild.api.auth.services import AuthService
    from vollbuild.core.extensions import db

    raw_token, member = AuthService.create_password_reset("admin@test.ch")
    db.session.commit()

    # Too short
    resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "password": "short123!"},
    )
    assert resp.status_code == 400
    assert resp.get_json().get("error") == "WEAK_PASSWORD"


def test_weak_password_rejected_on_change(client, seeded_db, auth_headers):
    """change-password rejects a weak new password."""
    resp = client.post(
        "/api/v1/account/change-password",
        json={"currentPassword": "password123", "newPassword": "short"},
    )
    assert resp.status_code == 400
    assert resp.get_json().get("error") == "WEAK_PASSWORD"


def test_zxcvbn_low_score_rejected_on_change(client, seeded_db, auth_headers):
    """change-password rejects a password with zxcvbn score < 3 even if long enough."""
    # 12+ chars but very common/predictable → low zxcvbn score
    resp = client.post(
        "/api/v1/account/change-password",
        json={"currentPassword": "password123", "newPassword": "password123456"},
    )
    assert resp.status_code == 400
    assert resp.get_json().get("error") == "WEAK_PASSWORD"


# ── must_change_password enforcement ──────────────────────────────────────────


def test_must_change_password_blocks_account_endpoint(client, seeded_db, db):
    """A member with must_change_password=True gets 403 on GET /account."""
    member = seeded_db["admin"]
    member.user.must_change_password = True
    db.session.commit()

    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )

    # GET /account/ uses @require_password_changed → 403
    resp = client.get("/api/v1/account/")
    assert resp.status_code == 403
    assert resp.get_json().get("error") == "MUST_CHANGE_PASSWORD"


def test_must_change_password_allows_logout(client, seeded_db, db):
    """must_change_password does NOT block logout (the escape hatch)."""
    member = seeded_db["admin"]
    member.user.must_change_password = True
    db.session.commit()

    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )

    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 204


def test_must_change_password_allows_change_password(client, seeded_db, db):
    """must_change_password does NOT block change-password (the escape hatch)."""
    member = seeded_db["admin"]
    member.user.must_change_password = True
    db.session.commit()

    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )

    resp = client.post(
        "/api/v1/account/change-password",
        json={
            "currentPassword": "password123",
            "newPassword": "new-strong-password-123!",
        },
    )
    assert resp.status_code == 200


# ── Cookie attributes in production mode ──────────────────────────────────────


def test_jwt_cookies_secure_in_production_mode(app, client, seeded_db):
    """JWT cookies have Secure flag when JWT_COOKIE_SECURE=True."""
    with patch.dict(app.config, {"JWT_COOKIE_SECURE": True}):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.ch", "password": "password123"},
        )
    assert resp.status_code == 200
    cookies = resp.headers.getlist("Set-Cookie")
    access_cookies = [c for c in cookies if "access_token_cookie=" in c]
    assert len(access_cookies) > 0
    assert "Secure" in access_cookies[0], "Access cookie must have Secure flag"


def test_jwt_cookies_httponly(app, client, seeded_db):
    """JWT access and refresh cookies are HttpOnly."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    assert resp.status_code == 200
    cookies = resp.headers.getlist("Set-Cookie")
    access = [c for c in cookies if "access_token_cookie=" in c]
    refresh = [c for c in cookies if "refresh_token_cookie=" in c]
    assert len(access) > 0 and "HttpOnly" in access[0]
    assert len(refresh) > 0 and "HttpOnly" in refresh[0]


def test_jwt_cookies_samesite_lax(app, client, seeded_db):
    """JWT cookies have SameSite=Lax."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    assert resp.status_code == 200
    cookies = resp.headers.getlist("Set-Cookie")
    access = [c for c in cookies if "access_token_cookie=" in c]
    assert len(access) > 0
    assert "SameSite=Lax" in access[0]


# ── Referrer-Policy header ────────────────────────────────────────────────────


def test_referrer_policy_header_present(client):
    """Referrer-Policy: strict-origin-when-cross-origin is set on all responses."""
    HealthCache.set({"status": "ok", "services": {}, "checked_at": 0})
    resp = client.get("/api/v1/health")
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_security_headers_on_error_response(client):
    """Security headers are present even on 404 responses."""
    resp = client.get("/api/v1/nonexistent-endpoint")
    assert resp.status_code == 404
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert "Referrer-Policy" in resp.headers


# ── forgot-password timing-safe (no enumeration) ──────────────────────────────


def test_forgot_password_unknown_email_returns_200(client, seeded_db):
    """forgot-password returns 200 for unknown emails (no account enumeration)."""
    resp = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nonexistent@test.ch"},
    )
    assert resp.status_code == 200
    assert resp.get_json().get("ok") is True


def test_forgot_password_known_email_returns_200(client, seeded_db):
    """forgot-password returns 200 for known emails (same as unknown)."""
    resp = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "admin@test.ch"},
    )
    assert resp.status_code == 200
    assert resp.get_json().get("ok") is True


def test_forgot_password_empty_email_returns_200(client, seeded_db):
    """forgot-password with empty email returns 200 (no validation leak)."""
    resp = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": ""},
    )
    assert resp.status_code == 200


# ── User-object handling (no Member profile) ──────────────────────────────────


def test_account_endpoint_returns_no_tenant_for_user_only(client, seeded_db, db):
    """GET /account/ returns noTenant=true for a User without a Member profile.

    This was the root cause of the cos↔sso redirect loop: the User object
    lacks must_change_password, causing a 500 in require_password_changed.
    """
    from vollbuild.core.models.user import User

    user = User(email="user-only@test.ch", first_name="User", last_name="Only")
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    client.post(
        "/api/v1/auth/login",
        json={"email": "user-only@test.ch", "password": "password123"},
    )

    resp = client.get("/api/v1/account/")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("noTenant") is True
    assert data["user"]["email"] == "user-only@test.ch"


def test_require_password_changed_passes_for_user_object(client, seeded_db, db):
    """require_password_changed decorator does not crash on User objects.

    User objects (from signup/login without a tenant) have no
    must_change_password attribute. The decorator must pass through
    instead of raising AttributeError → 500.
    """
    from vollbuild.core.models.user import User

    user = User(email="no-tenant@test.ch", first_name="No", last_name="Tenant")
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    client.post(
        "/api/v1/auth/login",
        json={"email": "no-tenant@test.ch", "password": "password123"},
    )

    # GET /account/ uses @require_password_changed — must not 500
    resp = client.get("/api/v1/account/")
    assert resp.status_code == 200
    assert resp.get_json().get("noTenant") is True


def test_permissions_endpoint_for_user_only(client, seeded_db, db):
    """GET /account/permissions works for a User without a Member profile."""
    from vollbuild.core.models.user import User

    user = User(email="perm-user@test.ch", first_name="Perm", last_name="User")
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()

    client.post(
        "/api/v1/auth/login",
        json={"email": "perm-user@test.ch", "password": "password123"},
    )

    resp = client.get("/api/v1/account/permissions")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("is_admin") is False
    assert data.get("permissions") == []
