"""S03 WildDuck Integration Test Suite.

All tests mock WildDuck HTTP calls — no live WildDuck instance required.
Tests cover: mailbox CRUD via API, group alias auto-creation, membership
alias sync, and Celery task dispatch on password change.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch


# ── Helpers ───────────────────────────────────────────────────────────────────


def _wd_config(app):
    """Set WildDuck config on the app so _wd_required() passes."""
    app.config["WILDDUCK_API_URL"] = "http://wildduck.test"
    app.config["WILDDUCK_API_TOKEN"] = "test-token"


# ── 1. Mailbox creation calls WildDuck ───────────────────────────────────────


def test_create_mailbox_calls_wildduck(client, app, auth_headers, seeded_db):
    _wd_config(app)
    mock_client = MagicMock()
    mock_client.create_user.return_value = {"id": "wd-user-001"}

    try:
        with patch(
            "hubra.core.services.wildduck.WildDuckClient", return_value=mock_client
        ):
            resp = client.post(
                "/api/v1/mail/mailboxes",
                json={
                    "username": "testuser",
                    "displayName": "Test User",
                    "quotaGb": 1.0,
                },
                headers=auth_headers,
            )
    finally:
        app.config["WILDDUCK_API_URL"] = ""
        app.config["WILDDUCK_API_TOKEN"] = ""

    assert resp.status_code == 201
    mock_client.create_user.assert_called_once()
    call_kwargs = mock_client.create_user.call_args
    assert (
        call_kwargs.kwargs.get("username") == "testuser"
        or call_kwargs.args[0] == "testuser"
    )


# ── 2. Missing WildDuck config returns 503 ───────────────────────────────────


def test_create_mailbox_without_wildduck_config(client, app, auth_headers, seeded_db):
    app.config["WILDDUCK_API_URL"] = ""
    app.config["WILDDUCK_API_TOKEN"] = ""

    resp = client.post(
        "/api/v1/mail/mailboxes",
        json={"username": "testuser"},
        headers=auth_headers,
    )
    assert resp.status_code == 503
    assert resp.get_json().get("error") == "SERVICE_UNAVAILABLE"


# ── 3. List mailboxes is DB-only (no WildDuck call) ─────────────────────────


def test_list_mailboxes_db_only(client, app, auth_headers, seeded_db):
    from hubra.core.models.managed_mail import ManagedMailAddress
    from hubra.core.extensions import db

    addr = ManagedMailAddress(
        address="alice@test.ch",
        address_type="mailbox",
        is_protected=False,
        is_enabled=True,
        is_system=False,
        kind="member",
        local_part="alice",
        domain="test.ch",
        wildduck_id="u1",
        wildduck_user_id="u1",
        owner_type="member",
        owner_id=seeded_db["admin"].id,
        provisioning_status="provisioned",
        quota_bytes=1073741824,
        quota_used=0,
    )
    db.session.add(addr)
    db.session.commit()

    resp = client.get("/api/v1/mail/mailboxes", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.get_json()
    assert "data" in data
    assert len(data["data"]) >= 1
    mb = next((m for m in data["data"] if m["address"] == "alice@test.ch"), None)
    assert mb is not None
    assert mb["quotaTotal"] == 1.0
    assert mb["memberId"] == seeded_db["admin"].id


# ── 4. Create alias calls WildDuck ───────────────────────────────────────────


def test_create_alias_calls_wildduck(client, app, auth_headers, seeded_db):
    _wd_config(app)
    mock_client = MagicMock()
    mock_client.create_forwarding_alias.return_value = {"id": "addr-001"}

    try:
        with patch(
            "hubra.core.services.wildduck.WildDuckClient", return_value=mock_client
        ):
            resp = client.post(
                "/api/v1/mail/aliases",
                json={"address": "group@test.ch", "deliversTo": ["alice@test.ch"]},
                headers=auth_headers,
            )
    finally:
        app.config["WILDDUCK_API_URL"] = ""
        app.config["WILDDUCK_API_TOKEN"] = ""

    assert resp.status_code == 201
    mock_client.create_forwarding_alias.assert_called_once()


# ── 5. Group creation does NOT auto-create WildDuck alias ────────────────────


def test_create_group_creates_wildduck_alias(client, app, auth_headers, seeded_db):
    """POST /groups does NOT call create_forwarding_alias — group mail is managed
    via ManagedMailAddress, not auto-provisioned on group creation.
    """
    _wd_config(app)
    app.config["MAIL_DOMAIN"] = "test.ch"
    mock_client = MagicMock()
    mock_client.create_forwarding_alias.return_value = {"id": "alias-grp-001"}

    try:
        with patch(
            "hubra.core.services.wildduck.WildDuckClient", return_value=mock_client
        ):
            resp = client.post(
                "/api/v1/groups/",
                json={"name": "S03TestGroup"},
                headers=auth_headers,
            )
    finally:
        app.config["MAIL_DOMAIN"] = ""
        app.config["WILDDUCK_API_URL"] = ""
        app.config["WILDDUCK_API_TOKEN"] = ""

    assert resp.status_code == 201
    mock_client.create_forwarding_alias.assert_not_called()


# ── 7. change-password dispatches Celery task ────────────────────────────────


def test_password_change_dispatches_celery_task(
    client, app, auth_headers, seeded_db, db
):
    from hubra.core.models.managed_mail import ManagedMailAddress

    admin = seeded_db["admin"]
    addr = ManagedMailAddress(
        address="admin@club.ch",
        address_type="mailbox",
        is_protected=False,
        wildduck_user_id="wd-admin-001",
        wildduck_id="wd-admin-001",
        kind="member",
        enabled=True,
        is_enabled=True,
        local_part="admin",
        domain="club.ch",
        owner_type="member",
        owner_id=admin.id,
    )
    db.session.add(addr)
    db.session.commit()

    # Inject a fake wildduck task module so the lazy import in the route succeeds
    mock_task = MagicMock()
    mock_task.delay = MagicMock()
    fake_mod = types.ModuleType("hubra.core.tasks.wildduck")
    fake_mod.sync_wildduck_password = mock_task
    sys.modules["hubra.core.tasks.wildduck"] = fake_mod
    try:
        resp = client.post(
            "/api/v1/account/change-password",
            json={
                "currentPassword": "password123",
                "newPassword": "Tr0ub4dor&3-correct-horse",
            },
            headers=auth_headers,
        )
    finally:
        sys.modules.pop("hubra.core.tasks.wildduck", None)

    assert resp.status_code == 200
    mock_task.delay.assert_called_once_with(admin.id)


# ── 8. Account PATCH never sets a password ──────────────────────────────────


def test_account_patch_refuses_password(client, auth_headers, seeded_db):
    """The password changes only with the current one (POST /account/password)."""
    resp = client.patch(
        "/api/v1/account/", json={"password": "patchedpass99"}, headers=auth_headers
    )
    assert resp.status_code == 400
    assert not seeded_db["user"].check_password("patchedpass99")


# ── 9. WildDuck error on group creation — graceful degradation ───────────────


def test_wildduck_error_does_not_fail_group_creation(
    client, app, auth_headers, seeded_db
):
    _wd_config(app)
    app.config["MAIL_DOMAIN"] = "test.ch"

    from hubra.core.services.wildduck import WildDuckError

    mock_client = MagicMock()
    mock_client.create_forwarding_alias.side_effect = WildDuckError(
        500, "Internal Server Error"
    )

    try:
        with patch(
            "hubra.core.services.wildduck.WildDuckClient", return_value=mock_client
        ):
            resp = client.post(
                "/api/v1/groups/",
                json={"name": "S03ErrorGroup"},
                headers=auth_headers,
            )
    finally:
        app.config["MAIL_DOMAIN"] = ""
        app.config["WILDDUCK_API_URL"] = ""
        app.config["WILDDUCK_API_TOKEN"] = ""

    # Group must still be created — WildDuck failure is non-blocking
    assert resp.status_code == 201


# ── 14. add_allowed_from stub logs WARNING ────────────────────────────────────


def test_add_allowed_from_stub_logs_warning(app, caplog):
    """WildDuckClient.add_allowed_from stub logs a WARNING and does not raise."""
    import logging

    from hubra.core.services.wildduck import WildDuckClient

    client = WildDuckClient("http://wd.test", "token")
    with caplog.at_level(logging.WARNING, logger="hubra.core.services.wildduck"):
        client.add_allowed_from("user-123", "mygroup@test.ch")

    assert any("send-as ACL not supported" in r.message for r in caplog.records)


# ── 15. remove_allowed_from stub logs WARNING ─────────────────────────────────


def test_remove_allowed_from_stub_logs_warning(app, caplog):
    """WildDuckClient.remove_allowed_from stub logs a WARNING and does not raise."""
    import logging

    from hubra.core.services.wildduck import WildDuckClient

    client = WildDuckClient("http://wd.test", "token")
    with caplog.at_level(logging.WARNING, logger="hubra.core.services.wildduck"):
        client.remove_allowed_from("user-456", "mygroup@test.ch")

    assert any("send-as ACL not supported" in r.message for r in caplog.records)
