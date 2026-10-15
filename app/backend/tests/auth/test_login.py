"""Tests for auth blueprint: login, refresh, logout, and bootstrap."""


# ── Login ─────────────────────────────────────────────────────────────────────


def test_login_success(client, seeded_db):
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@test.ch",
            "password": "password123",
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert "member" in body
    assert body["member"]["email"] == "admin@test.ch"


def test_login_wrong_password(client, seeded_db):
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@test.ch",
            "password": "wrongpassword",
        },
    )
    assert resp.status_code == 401


def test_login_unknown_email(client, seeded_db):
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "nobody@test.ch",
            "password": "password123",
        },
    )
    assert resp.status_code == 401


# ── Refresh ───────────────────────────────────────────────────────────────────


def test_refresh(client, seeded_db):
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )

    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200


# ── Logout ────────────────────────────────────────────────────────────────────


def test_logout_then_token_blocked(client, seeded_db):
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )

    # Logout succeeds
    logout_resp = client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 204

    # Cookies cleared — subsequent request is unauthenticated
    blocked_resp = client.get("/api/v1/account/")
    assert blocked_resp.status_code == 401


def test_login_creates_audit_entry(client, seeded_db):
    from vollbuild.core.extensions import db
    from vollbuild.core.models.audit import AuditEntry

    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    entries = db.session.scalars(
        db.select(AuditEntry).where(AuditEntry.action == "login")
    ).all()
    assert len(entries) == 1
    assert entries[0].actor_id == seeded_db["admin"].id
    assert entries[0].color is not None


# ── Keep signed in / remembered email ─────────────────────────────────────────


def test_login_keep_signed_in_sets_long_cookie(client, seeded_db):
    """keepSignedIn=true → refresh cookie Max-Age is 30 days (2592000s)."""
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@test.ch",
            "password": "password123",
            "keepSignedIn": True,
        },
    )
    assert resp.status_code == 200
    cookies = resp.headers.getlist("Set-Cookie")
    refresh_cookies = [c for c in cookies if "refresh_token_cookie" in c]
    assert len(refresh_cookies) == 1
    assert "Max-Age=2592000" in refresh_cookies[0]


def test_login_unchecked_sets_short_cookie(client, seeded_db):
    """keepSignedIn=false → refresh cookie Max-Age is 1 day (86400s)."""
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@test.ch",
            "password": "password123",
            "keepSignedIn": False,
        },
    )
    assert resp.status_code == 200
    cookies = resp.headers.getlist("Set-Cookie")
    refresh_cookies = [c for c in cookies if "refresh_token_cookie" in c]
    assert len(refresh_cookies) == 1
    assert "Max-Age=86400" in refresh_cookies[0]


def test_login_sets_remembered_email_cookie(client, seeded_db):
    """Login sets a remembered_email cookie with the email value."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    assert resp.status_code == 200
    cookies = resp.headers.getlist("Set-Cookie")
    email_cookies = [c for c in cookies if "remembered_email" in c]
    assert len(email_cookies) == 1
    assert "admin@test.ch" in email_cookies[0]
    assert "Max-Age=2592000" in email_cookies[0]


def test_logout_clears_remembered_email(client, seeded_db):
    """Logout deletes the remembered_email cookie."""
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    logout_resp = client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 204
    cookies = logout_resp.headers.getlist("Set-Cookie")
    email_cookies = [c for c in cookies if "remembered_email" in c]
    assert len(email_cookies) == 1
    assert "Max-Age=0" in email_cookies[0] or "delete" in email_cookies[0].lower()
