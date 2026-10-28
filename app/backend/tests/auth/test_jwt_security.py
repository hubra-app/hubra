"""JWT security tests — token validation, expiry, tampering, and refresh rotation.

Covers issue #131 — Security Tests for Authentication, JWT section:
- Invalid signature rejected
- Expired token rejected with 401
- Malformed token rejected
- Missing token on protected endpoint returns 401
- Refresh token rotation produces valid new tokens
- Reused refresh token detected and blocked
"""

from __future__ import annotations

from datetime import timedelta

from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    decode_token,
)
from unittest.mock import patch

from hubra.core.extensions import db
from hubra.core.models.token import TokenBlocklist


# ── Missing token on protected endpoint ───────────────────────────────────────


def test_missing_token_returns_401(client, seeded_db):
    """GET /account without any JWT cookie returns 401."""
    resp = client.get("/api/v1/account/")
    assert resp.status_code == 401


def test_missing_token_on_protected_post_returns_401(client, seeded_db):
    """POST /auth/logout without JWT returns 401."""
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 401


# ── Malformed token rejected ──────────────────────────────────────────────────


def test_malformed_token_rejected(client, seeded_db):
    """A garbage string as JWT cookie is rejected with 401."""
    client.set_cookie("access_token_cookie", "not.a.valid.jwt.token")
    resp = client.get("/api/v1/account/")
    assert resp.status_code == 401


def test_partial_jwt_rejected(client, seeded_db):
    """A truncated JWT is rejected with 401."""
    client.set_cookie("access_token_cookie", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIx")
    resp = client.get("/api/v1/account/")
    assert resp.status_code == 401


def test_empty_token_rejected(client, seeded_db):
    """An empty JWT cookie value is rejected."""
    client.set_cookie("access_token_cookie", "")
    resp = client.get("/api/v1/account/")
    assert resp.status_code == 401


# ── Invalid signature rejected ────────────────────────────────────────────────


def test_tampered_token_signature_rejected(app, client, seeded_db):
    """A token signed with a different secret is rejected."""
    # Create a token with the correct key, then tamper with the signature
    with app.app_context():
        token = create_access_token(identity="1")
    # Flip the last character of the signature to invalidate it
    parts = token.rsplit(".", 1)
    tampered = f"{parts[0]}.{'X' if parts[1][-1] != 'X' else 'Y'}"
    client.set_cookie("access_token_cookie", tampered)
    resp = client.get("/api/v1/account/")
    assert resp.status_code == 401


def test_token_wrong_secret_rejected(app, client, seeded_db):
    """A token created with a different JWT_SECRET_KEY is rejected."""
    with patch.dict(app.config, {"JWT_SECRET_KEY": "different-secret-key-32-bytes!!"}):
        with app.app_context():
            token = create_access_token(identity="1")
    client.set_cookie("access_token_cookie", token)
    resp = client.get("/api/v1/account/")
    assert resp.status_code == 401


# ── Expired token rejected ────────────────────────────────────────────────────


def test_expired_access_token_rejected(app, client, seeded_db):
    """An expired access token is rejected with 401."""
    with patch.dict(
        app.config,
        {"JWT_ACCESS_TOKEN_EXPIRES": timedelta(seconds=-1)},
    ):
        with app.app_context():
            token = create_access_token(identity=str(seeded_db["admin"].id))
    client.set_cookie("access_token_cookie", token)
    resp = client.get("/api/v1/account/")
    assert resp.status_code == 401


def test_expired_refresh_token_rejected(app, client, seeded_db):
    """An expired refresh token is rejected with 401 on /auth/refresh."""
    with patch.dict(
        app.config,
        {"JWT_REFRESH_TOKEN_EXPIRES": timedelta(seconds=-1)},
    ):
        with app.app_context():
            token = create_refresh_token(identity=str(seeded_db["admin"].id))
    client.set_cookie("refresh_token_cookie", token)
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


# ── Refresh token rotation ────────────────────────────────────────────────────


def test_refresh_produces_valid_access_token(client, seeded_db):
    """POST /auth/refresh returns 200 and sets a new access cookie."""
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200
    assert resp.get_json().get("ok") is True
    # Verify the new access token works
    resp2 = client.get("/api/v1/account/")
    assert resp2.status_code == 200


def test_reused_refresh_token_after_rotation_blocked(app, client, seeded_db):
    """After using a refresh token, using it again after logout should fail.

    The logout endpoint blocks the refresh token's jti in TokenBlocklist.
    A subsequent refresh attempt with the same token should be rejected.
    """
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    assert login.status_code == 200

    # Extract the refresh token from cookies
    refresh_token = None
    for header in login.headers.getlist("Set-Cookie"):
        if header.startswith("refresh_token_cookie="):
            refresh_token = header.split(";")[0].split("=", 1)[1]
            break
    assert refresh_token, "refresh_token_cookie must be set on login"

    # Decode to get jti
    with app.app_context():
        decoded = decode_token(refresh_token)
        jti = decoded["jti"]

    # Logout with the refresh token — this blocks it
    resp = client.post(
        "/api/v1/auth/logout",
        json={"refreshToken": refresh_token},
    )
    assert resp.status_code == 204

    # Verify the jti is in the blocklist
    with app.app_context():
        blocked = db.session.scalar(
            db.select(TokenBlocklist).where(TokenBlocklist.jti == jti)
        )
        assert blocked is not None, (
            "Refresh token jti must be in TokenBlocklist after logout"
        )

    # Set the refresh cookie back and try to use it — should be rejected
    client.set_cookie("refresh_token_cookie", refresh_token)
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


# ── Access token works after refresh ──────────────────────────────────────────


def test_access_token_invalidated_after_logout(client, seeded_db):
    """After logout, the access token is blocked (session revoked or jti blocked)."""
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )

    # Verify access works
    resp = client.get("/api/v1/account/")
    assert resp.status_code == 200

    # Logout
    client.post("/api/v1/auth/logout")

    # Access should now fail
    resp = client.get("/api/v1/account/")
    assert resp.status_code == 401
