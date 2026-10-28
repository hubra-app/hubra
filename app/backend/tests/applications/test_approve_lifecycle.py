"""S05 Member Lifecycle Automation Test Suite.

Tests cover: approve → Member created with must_change_password=True →
Celery tasks dispatched for WildDuck mailbox creation and welcome email →
login surfaces must_change_password flag → protected route returns 403 until
password changed → change-password clears flag → subsequent login succeeds.

All external calls (WildDuck, email) are mocked — no live services required.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch


# ── Helpers ───────────────────────────────────────────────────────────────────


def _seed_application(db):
    """Create a pending application and return it."""
    from vollbuild.core.models.application import Application

    app = Application(name="New Member", email="newmember@test.ch")
    db.session.add(app)
    db.session.commit()
    return app


def _seed_admin_role_and_tier(db):
    """Ensure a 'Member' role and default tier exist for approve_application."""
    from sqlalchemy import select
    from vollbuild.core.models.member import MembershipTier
    from vollbuild.core.models.role import Role

    role = db.session.scalar(select(Role).where(Role.name == "Member"))
    if role is None:
        role = Role(name="Member", is_default=False)
        db.session.add(role)

    tier = db.session.scalar(select(MembershipTier))
    if tier is None:
        tier = MembershipTier(name="Standard", price_chf=30, color="#6366f1")
        db.session.add(tier)

    db.session.commit()
    return role, tier


# ── 1. approve creates member with must_change_password=True ─────────────────


def test_approve_creates_member_with_must_change_password(
    client, app, auth_headers, seeded_db, db
):
    application = _seed_application(db)
    _seed_admin_role_and_tier(db)

    # Mock WildDuck and email so approve_application doesn't blow up
    with (
        patch("vollbuild.core.services.wildduck.try_get_client", return_value=None),
        patch("vollbuild.core.services.email._send"),
    ):
        resp = client.post(
            f"/api/v1/applications/{application.id}/approve",
            headers=auth_headers,
        )

    assert resp.status_code == 201
    data = resp.get_json()
    assert data.get("must_change_password") is True


# ── 2. approve dispatches WildDuck Celery task ────────────────────────────────


def test_approve_dispatches_wildduck_task(client, app, auth_headers, seeded_db, db):
    application = _seed_application(db)
    _seed_admin_role_and_tier(db)
    app.config["MAIL_DOMAIN"] = "test.ch"
    app.config["WILDDUCK_API_URL"] = "http://wildduck.test"
    app.config["WILDDUCK_API_TOKEN"] = "test-token"

    # Mock the Celery task module via sys.modules injection
    mock_create_task = MagicMock()
    mock_create_task.delay = MagicMock()
    fake_wildduck_tasks = types.ModuleType("vollbuild.core.tasks.wildduck")
    fake_wildduck_tasks.sync_wildduck_password = MagicMock()
    fake_wildduck_tasks.create_wildduck_user = mock_create_task
    sys.modules["vollbuild.core.tasks.wildduck"] = fake_wildduck_tasks

    try:
        with patch("vollbuild.core.services.email._send"):
            resp = client.post(
                f"/api/v1/applications/{application.id}/approve",
                headers=auth_headers,
            )
    finally:
        sys.modules.pop("vollbuild.core.tasks.wildduck", None)
        app.config["MAIL_DOMAIN"] = ""
        app.config["WILDDUCK_API_URL"] = ""
        app.config["WILDDUCK_API_TOKEN"] = ""

    assert resp.status_code == 201
    mock_create_task.delay.assert_called_once()
    call_args = mock_create_task.delay.call_args
    # First positional arg should be the member_id (int)
    assert isinstance(call_args.args[0], int)


# ── 3. approve dispatches welcome email ───────────────────────────────────────


def test_approve_dispatches_welcome_email(client, app, auth_headers, seeded_db, db):
    application = _seed_application(db)
    _seed_admin_role_and_tier(db)

    # Mock the email Celery task module
    mock_email_task = MagicMock()
    mock_email_task.delay = MagicMock()
    fake_email_tasks = types.ModuleType("vollbuild.core.tasks.email_tasks")
    fake_email_tasks.send_email_task = mock_email_task
    sys.modules["vollbuild.core.tasks.email_tasks"] = fake_email_tasks

    try:
        with (
            patch("vollbuild.core.services.wildduck.try_get_client", return_value=None),
            patch("vollbuild.core.services.email._send") as mock_send,
        ):
            resp = client.post(
                f"/api/v1/applications/{application.id}/approve",
                headers=auth_headers,
            )
            # Email service should be called (either directly or via task)
            email_sent = mock_send.called or mock_email_task.delay.called
    finally:
        sys.modules.pop("vollbuild.core.tasks.email_tasks", None)

    assert resp.status_code == 201
    assert email_sent, "Welcome email must be sent (via _send or send_email_task.delay)"


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
    with patch("vollbuild.core.services.email._send"):
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
    with patch("vollbuild.core.services.email._send"):
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
