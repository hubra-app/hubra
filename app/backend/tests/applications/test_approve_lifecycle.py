"""S05 Member Lifecycle Automation Test Suite.

Tests cover: login surfaces must_change_password flag → protected route
returns 403 until password changed → change-password clears flag →
subsequent login succeeds. (Approving an application without an account
sends an invite; see tests/members/test_invites.py.)

All external calls (WildDuck, email) are mocked — no live services required.
"""

from __future__ import annotations

from unittest.mock import patch


# ── 4. login surfaces must_change_password flag ───────────────────────────────


def test_login_surfaces_must_change_password_flag(client, app, seeded_db, db):

    # Set must_change_password on the seeded admin
    admin = seeded_db["admin"]
    admin.user.must_change_password = True
    db.session.commit()

    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@test.ch",
            "password": "password123",
        },
    )

    assert resp.status_code == 200
    data = resp.get_json()
    # The flag should appear either as mustChangePassword (camelCase) or
    # must_change_password (snake_case via member schema)
    flag = data.get("mustChangePassword") or data.get("member", {}).get(
        "must_change_password"
    )
    assert flag is True, (
        f"Expected must_change_password=True in login response, got: {data}"
    )


# ── 5. protected route blocked while must_change_password is set ──────────────


def test_protected_route_blocked_while_must_change_password(client, app, seeded_db, db):

    # Set must_change_password on the seeded admin
    admin = seeded_db["admin"]
    admin.user.must_change_password = True
    db.session.commit()

    # Log in — should succeed
    login_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@test.ch",
            "password": "password123",
        },
    )
    assert login_resp.status_code == 200
    headers = {}

    # GET /api/v1/account should return 403 MUST_CHANGE_PASSWORD
    resp = client.get("/api/v1/account/", headers=headers)
    assert resp.status_code == 403
    data = resp.get_json()
    assert data.get("error") == "MUST_CHANGE_PASSWORD"


# ── 6. change-password clears must_change_password flag ──────────────────────


def test_change_password_clears_flag(client, app, seeded_db, db):

    # Set must_change_password on the seeded admin
    admin = seeded_db["admin"]
    admin.user.must_change_password = True
    db.session.commit()

    # Log in to get token
    login_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@test.ch",
            "password": "password123",
        },
    )
    assert login_resp.status_code == 200
    headers = {}

    # Change password — must NOT be blocked by the gate
    with patch("hubra.core.services.email._send"):
        resp = client.post(
            "/api/v1/account/change-password",
            json={"currentPassword": "password123", "newPassword": "newsecurepass1"},
            headers=headers,
        )

    assert resp.status_code == 200

    # Verify flag is cleared in DB
    db.session.refresh(admin)
    assert admin.must_change_password is False


# ── 7. login succeeds and access is granted after password change ─────────────


def test_login_succeeds_after_password_change(client, app, seeded_db, db):

    # Set must_change_password
    admin = seeded_db["admin"]
    admin.user.must_change_password = True
    db.session.commit()

    # Login to get token
    login_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@test.ch",
            "password": "password123",
        },
    )
    assert login_resp.status_code == 200
    headers = {}

    # Change password (escape hatch — must work despite gate)
    with patch("hubra.core.services.email._send"):
        change_resp = client.post(
            "/api/v1/account/change-password",
            json={"currentPassword": "password123", "newPassword": "newsecurepass1"},
            headers=headers,
        )
    assert change_resp.status_code == 200

    # Login again with new password
    login2_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@test.ch",
            "password": "newsecurepass1",
        },
    )
    assert login2_resp.status_code == 200
    headers2 = {}

    # Now GET /api/v1/account should succeed (200)
    account_resp = client.get("/api/v1/account/", headers=headers2)
    assert account_resp.status_code == 200
