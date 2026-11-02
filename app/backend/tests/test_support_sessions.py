"""Support sessions: impersonation with a chosen time limit, the log in
manage › Support-Zugriffe, and ending a running session from there."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from hubra.core.models.tenant import GlobalAuditEntry
from tests.test_impersonation_api import superadmin_db, target_tenant  # noqa: F401

LIST = "/api/v1/system/support-sessions"


def _login(client):
    resp = client.post(
        "/api/v1/auth/login", json={"email": "admin@test.ch", "password": "password123"}
    )
    assert resp.status_code == 200


@pytest.fixture
def staff(app, superadmin_db):  # noqa: F811
    """Two browsers of the same platform admin: one opens the club, the
    other looks at the log."""
    a, b = app.test_client(), app.test_client()
    _login(a)
    _login(b)
    return a, b


def _start(client, target, **body):
    return client.post(
        f"/api/v1/system/tenants/{target['tenant'].id}/impersonate",
        json={"reason": "Ticket #7", "user_id": target["user"].id, **body},
    )


def test_minutes_are_chosen_and_logged(staff, target_tenant, db):  # noqa: F811
    a, _ = staff
    resp = _start(a, target_tenant, minutes=60)
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["minutes"] == 60
    expires = datetime.fromisoformat(body["expires_at"])
    assert (
        timedelta(minutes=59)
        < expires - datetime.now(timezone.utc)
        <= timedelta(minutes=60)
    )

    entry = db.session.scalar(
        select(GlobalAuditEntry).where(GlobalAuditEntry.action == "impersonation.start")
    )
    assert entry.details["session"] == body["session"]
    assert entry.details["minutes"] == 60


@pytest.mark.parametrize("minutes", [5, 600, "30", True])
def test_other_lengths_are_refused(staff, target_tenant, minutes):  # noqa: F811
    a, _ = staff
    assert _start(a, target_tenant, minutes=minutes).status_code == 422


def test_log_lists_and_ends_a_running_session(staff, target_tenant, db):  # noqa: F811
    a, b = staff
    started = _start(a, target_tenant, minutes=15).get_json()
    assert a.get("/api/v1/account/permissions").status_code == 200

    body = b.get(LIST).get_json()
    assert body["active"] == 1
    (row,) = body["sessions"]
    assert row["status"] == "active"
    assert row["session"] == started["session"]
    assert row["club"] == "Target Club"
    assert row["staff"]["email"] == "admin@test.ch"
    assert row["member"]["email"] == "target@test.ch"
    assert row["reason"] == "Ticket #7"
    assert row["mode"] == "read"
    assert row["minutes"] == 15

    resp = b.post(f"{LIST}/{started['session']}/end")
    assert resp.status_code == 200, resp.get_json()
    # The impersonating browser is out from its next request on.
    assert a.get("/api/v1/account/permissions").status_code == 401

    (row,) = b.get(LIST).get_json()["sessions"]
    assert row["status"] == "revoked"
    assert row["ended_by"]["email"] == "admin@test.ch"
    assert b.get(LIST, query_string={"status": "active"}).get_json()["sessions"] == []
    assert b.post(f"{LIST}/{started['session']}/end").status_code == 409
    assert b.post(f"{LIST}/nope/end").status_code == 404


def test_stopping_yourself_closes_the_session(staff, target_tenant):  # noqa: F811
    a, b = staff
    _start(a, target_tenant, allow_changes=True)
    assert a.post("/api/v1/system/impersonation/stop").status_code == 200
    (row,) = b.get(LIST).get_json()["sessions"]
    assert row["status"] == "ended"
    assert row["mode"] == "act"
    assert row["ended_by"] is None


def test_old_sessions_without_an_id_expire(staff, target_tenant, db):  # noqa: F811
    _, b = staff
    db.session.add(
        GlobalAuditEntry(
            tenant_id=target_tenant["tenant"].id,
            action="impersonation.start",
            target_type="Member",
            target_id="1",
            details={"reason": "old"},
            time=datetime.now(timezone.utc) - timedelta(hours=3),
        )
    )
    db.session.commit()
    (row,) = b.get(LIST).get_json()["sessions"]
    assert row["status"] == "expired"
    assert row["seconds"] == 30 * 60


def test_needs_audit_rights(client, auth_headers):
    assert client.get(LIST).status_code in (401, 403)


def test_starts_with_only_the_account_cookie(app, superadmin_db, target_tenant):  # noqa: F811
    """manage signed in through SSO may hold only the account_token cookie:
    starting a support session must not need a standard access cookie."""
    c = app.test_client()
    _login(c)
    c.delete_cookie("access_token_cookie")
    c.delete_cookie("refresh_token_cookie")
    assert c.get_cookie("access_token_cookie") is None
    resp = _start(c, target_tenant)
    assert resp.status_code == 200, resp.get_json()
