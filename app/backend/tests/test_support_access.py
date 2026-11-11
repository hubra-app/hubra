"""Support access as the club sees it: entries in the club's audit log, and
the club setting that makes Hubra staff ask first (services.support_access)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select

from hubra.core.models.audit import AuditEntry
from hubra.core.models.support_access import SupportAccessRequest
from tests.test_impersonation_api import superadmin_db, target_tenant  # noqa: F401

CLUB = "/api/v1/admin/support-access"


def _login(client):
    resp = client.post(
        "/api/v1/auth/login", json={"email": "admin@test.ch", "password": "password123"}
    )
    assert resp.status_code == 200


def _require(db, tenant, on=True):
    settings = dict(tenant.settings or {})
    settings["branding"] = {
        **settings.get("branding", {}),
        "support_requires_approval": on,
    }
    tenant.settings = settings
    db.session.commit()


@pytest.fixture
def setup(app, db, superadmin_db, target_tenant):  # noqa: F811
    """A platform admin in manage (``staff``) and a club admin of the target
    club (``club``)."""
    staff, club = app.test_client(), app.test_client()
    _login(staff)
    _login(club)
    with (
        patch(
            "hubra.api.admin.routes.current_tenant",
            return_value=target_tenant["tenant"],
        ),
        patch("hubra.core.tenant.context.set_search_path"),
    ):
        yield staff, club, target_tenant


def _base(target):
    return f"/api/v1/system/tenants/{target['tenant'].id}"


def _start(client, target, **body):
    return client.post(
        f"{_base(target)}/impersonate",
        json={"reason": "Ticket #7", "user_id": target["user"].id, **body},
    )


def _ask(client, target, **body):
    return client.post(
        f"{_base(target)}/support-access",
        json={"reason": "Ticket #8", "minutes": 15, **body},
    )


def _club_log(db) -> list[tuple[str, str]]:
    return [
        (e.action, e.target_label or "")
        for e in db.session.scalars(
            select(AuditEntry)
            .where(AuditEntry.action.like("support_%"))
            .order_by(AuditEntry.id)
        ).all()
    ]


def test_every_session_lands_in_the_clubs_log(setup, db):
    staff, _, target = setup
    assert _start(staff, target, allow_changes=True, minutes=30).status_code == 200
    assert staff.post("/api/v1/system/impersonation/stop").status_code == 200
    log = _club_log(db)
    assert [a for a, _ in log] == ["support_session_change", "support_session_end"]
    assert "Target User · 30 min · Ticket #7" == log[0][1]
    entry = db.session.scalar(
        select(AuditEntry).where(AuditEntry.action == "support_session_change")
    )
    assert entry.actor_id is None and entry.actor_name.startswith("Hubra support")


def test_a_club_that_asks_first_refuses_a_session_without_approval(setup, db):
    staff, _, target = setup
    _require(db, target["tenant"])
    resp = _start(staff, target)
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "SUPPORT_APPROVAL_REQUIRED"
    assert _club_log(db) == []


def test_ask_approve_and_use_once(setup, db):
    staff, club, target = setup
    _require(db, target["tenant"])
    state = staff.get(f"{_base(target)}/support-access").get_json()
    assert state["requiresApproval"] is True and state["request"] is None

    resp = _ask(staff, target, allow_changes=False)
    assert resp.status_code == 201, resp.get_json()
    req = resp.get_json()
    assert req["status"] == "pending"
    assert _ask(staff, target).status_code == 409

    listed = club.get(CLUB).get_json()
    assert listed["requiresApproval"] is True
    assert [r["id"] for r in listed["requests"]] == [req["id"]]

    resp = club.post(f"{CLUB}/{req['id']}/approve")
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["status"] == "approved"
    assert club.post(f"{CLUB}/{req['id']}/decline").status_code == 409

    # The session runs as asked for, whatever the body says.
    resp = _start(staff, target, request_id=req["id"], minutes=120, allow_changes=True)
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["minutes"] == 15 and body["read_only"] is True
    assert db.session.get(SupportAccessRequest, req["id"]).status == "used"

    staff.post("/api/v1/system/impersonation/stop")
    # Used once: the same approval doesn't open the club again.
    assert _start(staff, target, request_id=req["id"]).status_code == 403
    assert [a for a, _ in _club_log(db)] == [
        "support_access_request",
        "support_access_approve",
        "support_session_view",
        "support_session_end",
    ]


def test_a_declined_or_old_approval_opens_nothing(setup, db):
    staff, club, target = setup
    _require(db, target["tenant"])
    first = _ask(staff, target).get_json()
    assert club.post(f"{CLUB}/{first['id']}/decline").get_json()["status"] == "declined"
    assert _start(staff, target, request_id=first["id"]).status_code == 403

    second = _ask(staff, target).get_json()
    club.post(f"{CLUB}/{second['id']}/approve")
    req = db.session.get(SupportAccessRequest, second["id"])
    req.decided_at = datetime.now(timezone.utc) - timedelta(hours=25)
    db.session.commit()
    assert (
        staff.get(f"{_base(target)}/support-access").get_json()["request"]["status"]
        == "expired"
    )
    assert _start(staff, target, request_id=second["id"]).status_code == 403


def test_staff_inside_the_club_cannot_let_themselves_in(setup, db):
    staff, _, target = setup
    req = _ask(staff, target).get_json()
    _require(db, target["tenant"], on=False)
    assert _start(staff, target, allow_changes=True).status_code == 200
    # Now a club admin by impersonation: approving or switching the rule is refused.
    resp = staff.post(f"{CLUB}/{req['id']}/approve")
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "IMPERSONATION_RESTRICTED"
    resp = staff.patch(
        "/api/v1/admin/club-settings", json={"support_requires_approval": True}
    )
    assert resp.status_code == 403
    # Saving the form with the rule unchanged still works.
    resp = staff.patch(
        "/api/v1/admin/club-settings", json={"support_requires_approval": False}
    )
    assert resp.status_code == 200, resp.get_json()


def test_club_admins_set_the_rule(setup, db):
    _, club, target = setup
    resp = club.patch(
        "/api/v1/admin/club-settings", json={"support_requires_approval": True}
    )
    assert resp.status_code == 200, resp.get_json()
    db.session.refresh(target["tenant"])
    assert target["tenant"].settings["branding"]["support_requires_approval"] is True


def test_sign_in_is_needed(app, db, superadmin_db, target_tenant):  # noqa: F811
    anon = app.test_client()
    assert anon.get(CLUB).status_code == 401
    assert anon.post(f"{CLUB}/1/approve").status_code == 401
    assert anon.get(f"{_base(target_tenant)}/support-access").status_code in (401, 403)
    assert _ask(anon, target_tenant).status_code in (401, 403)


def test_members_cannot_ask(app, db, superadmin_db, target_tenant):  # noqa: F811
    member = app.test_client()
    resp = member.post(
        "/api/v1/auth/login",
        json={"email": "target@test.ch", "password": "targetpass123"},
    )
    assert resp.status_code == 200
    # Not platform staff: manage's endpoints are closed.
    assert member.get(f"{_base(target_tenant)}/support-access").status_code == 403
    assert _ask(member, target_tenant).status_code == 403


def test_ending_a_session_in_manage_shows_in_the_club(setup, db):
    staff, _, target = setup
    other = setup[1]
    started = _start(staff, target).get_json()
    resp = other.post(f"/api/v1/system/support-sessions/{started['session']}/end")
    assert resp.status_code == 200, resp.get_json()
    assert [a for a, _ in _club_log(db)] == [
        "support_session_view",
        "support_session_revoked",
    ]


def test_the_deciding_admin_is_the_actor(setup, db):
    staff, club, target = setup
    _require(db, target["tenant"])
    req = _ask(staff, target).get_json()
    club.post(f"{CLUB}/{req['id']}/approve")
    entry = db.session.scalar(
        select(AuditEntry).where(AuditEntry.action == "support_access_approve")
    )
    assert entry.actor_id is not None
    assert not (entry.actor_name or "").startswith("Hubra support")
    assert entry.target_type == "Support"
