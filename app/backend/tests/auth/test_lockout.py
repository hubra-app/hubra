"""Tests for account lockout after repeated failed login attempts."""

from __future__ import annotations


# ── 1. Lockout after 5 failures ───────────────────────────────────────────────


def test_lockout_after_five_failures(client, seeded_db):
    """First 5 bad attempts → 401; 6th → 403 ACCOUNT_LOCKED.

    The route increments the counter and sets locked_until on attempt 5 but
    still raises 401 for that request; the lockout guard fires on attempt 6.
    """
    url = "/api/v1/auth/login"
    payload = {"email": "admin@test.ch", "password": "WRONG"}

    for i in range(5):
        resp = client.post(url, json=payload)
        assert resp.status_code == 401, (
            f"attempt {i + 1}: expected 401, got {resp.status_code}"
        )

    resp = client.post(url, json=payload)
    assert resp.status_code == 403
    data = resp.get_json()
    assert data.get("error") == "ACCOUNT_LOCKED"


# ── 2. Locked account rejects correct password ───────────────────────────────


def test_locked_account_cannot_login_with_correct_password(client, seeded_db):
    """After lockout is triggered (5 failures), correct password still returns 403."""
    url = "/api/v1/auth/login"
    wrong = {"email": "admin@test.ch", "password": "WRONG"}

    # 5 failures set locked_until; 6th attempt triggers the lockout guard.
    for _ in range(5):
        client.post(url, json=wrong)

    # Attempt 6 with the correct password — lockout guard fires first.
    resp = client.post(url, json={"email": "admin@test.ch", "password": "password123"})
    assert resp.status_code == 403
    assert resp.get_json().get("error") == "ACCOUNT_LOCKED"


# ── 3. Disabled account login rejected ────────────────────────────────────────


def test_disabled_account_login_rejected(client, seeded_db):
    """A disabled member account returns 403 ACCOUNT_DISABLED on login.

    Note: authenticate() (Member path) checks is_disabled. authenticate_user()
    (User path) does not, but the login route falls back to authenticate()
    when authenticate_user raises, and the seeded admin has no User record.
    """
    member = seeded_db["admin"]
    member.user.is_disabled = True
    from vollbuild.extensions import db

    db.session.commit()

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    assert resp.status_code == 403
    assert resp.get_json().get("error") == "ACCOUNT_DISABLED"
