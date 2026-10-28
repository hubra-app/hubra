"""Tests for auth refresh endpoint with locked accounts."""

from datetime import datetime, timedelta, timezone


# ── Refresh lockout tests ─────────────────────────────────────────────────────


def test_refresh_returns_200_for_unlocked_account(client, seeded_db):
    """A normal (unlocked) account gets a fresh access token from /auth/refresh."""
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200


def test_refresh_returns_403_for_locked_account(client, seeded_db, db):
    """A locked account cannot renew its access token via /auth/refresh."""
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )

    member = seeded_db["admin"]
    member.user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
    db.session.add(member.user)
    db.session.commit()

    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 403
    body = resp.get_json()
    assert body.get("error") == "ACCOUNT_LOCKED"
