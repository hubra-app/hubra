"""Tests for forgot-password, reset-password, and change-password flows."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone


# ── 1. forgot-password always returns 200 for unknown email ──────────────────


def test_forgot_password_always_200(client, seeded_db):
    """Unknown email must still return 200 (no email-enumeration)."""
    resp = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nobody@example.com"},
    )
    assert resp.status_code == 200
    assert resp.get_json().get("ok") is True


# ── 2. forgot-password creates a token for a known email ─────────────────────


def test_forgot_password_creates_token(client, seeded_db, db):
    """A known member's forgot-password request creates a PasswordResetToken."""
    from sqlalchemy import select
    from hubra.core.models.password_reset import PasswordResetToken

    resp = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "admin@test.ch"},
    )
    assert resp.status_code == 200

    with db.engine.connect() as conn:
        count = conn.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == seeded_db["admin"].user_id
            )
        ).fetchall()
    assert len(count) >= 1


# ── 3. reset-password with invalid token → 400 ───────────────────────────────


def test_reset_password_with_invalid_token(client, seeded_db):
    """A garbage token must return 400 INVALID_TOKEN."""
    resp = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": "totally-invalid-garbage",
            "password": "Tr0ub4dor&3-correct-horse",
        },
    )
    assert resp.status_code == 400
    assert resp.get_json().get("error") == "INVALID_TOKEN"


# ── 4. Full reset-password flow ───────────────────────────────────────────────


def test_reset_password_flow(client, seeded_db, db):
    """Create a PasswordResetToken in the DB, call reset-password, assert success."""
    from hubra.core.models.password_reset import PasswordResetToken

    admin = seeded_db["admin"]
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    reset_token = PasswordResetToken(
        user_id=admin.user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.session.add(reset_token)
    db.session.commit()

    new_password = "SuperNew!Pass1"
    resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "password": new_password},
    )
    assert resp.status_code == 200
    assert resp.get_json().get("ok") is True

    # Verify password actually changed
    db.session.refresh(admin)
    assert admin.user.check_password(new_password) is True


# ── 5. change-password with wrong current password → 401 ────────────────────


def test_change_password_wrong_current(client, seeded_db, auth_headers):
    """Wrong currentPassword must return 401."""
    resp = client.post(
        "/api/v1/account/change-password",
        json={"currentPassword": "WRONG", "newPassword": "doesnotmatter1"},
        headers=auth_headers,
    )
    assert resp.status_code == 401
    assert resp.get_json().get("error") == "UNAUTHORIZED"


# ── 6. change-password success and subsequent login ──────────────────────────


def test_change_password_success(client, seeded_db, auth_headers):
    """Correct current password + valid new password → 200; subsequent login succeeds."""
    new_password = "Changed!Pass99"
    resp = client.post(
        "/api/v1/account/change-password",
        json={"currentPassword": "password123", "newPassword": new_password},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json().get("ok") is True

    # Verify new credentials work
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": new_password},
    )
    assert login_resp.status_code == 200
    assert "member" in login_resp.get_json()
