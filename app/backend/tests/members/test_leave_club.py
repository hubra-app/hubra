"""Members leaving a club, with and without the club's approval."""

from __future__ import annotations

import pytest

from hubra.core.models.member import Member
from hubra.core.models.role import Role
from hubra.core.models.tenant import Tenant
from hubra.core.models.user import User
from hubra.core.models.user_tenant import UserTenant

H = {"X-Tenant-Slug": "club-a"}


@pytest.fixture
def club(db, seeded_db):
    t = Tenant(name="Club A", slug="club-a", status="active", settings={})
    db.session.add(t)
    db.session.flush()
    member_role = Role(name="Member", is_default=False)
    user = User(email="anna@test.ch", first_name="Anna", last_name="M")
    user.set_password("password123")
    db.session.add_all([member_role, user])
    db.session.flush()
    anna = Member(user_id=user.id, status="active", tier_id=seeded_db["tier"].id)
    anna.roles = [member_role]
    db.session.add(anna)
    db.session.add_all(
        [
            UserTenant(user_id=user.id, tenant_id=t.id),
            UserTenant(user_id=seeded_db["user"].id, tenant_id=t.id, is_owner=True),
        ]
    )
    db.session.commit()
    return {"tenant": t, "anna": anna, "user": user}


def _login(client, email):
    client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
        headers=H,
    )


def _needs_approval(db, tenant, on: bool):
    tenant.settings = {"branding": {"leave_requires_approval": on}}
    db.session.commit()


def test_member_leaves_at_once_by_default(client, db, club):
    _login(client, "anna@test.ch")
    assert client.get("/api/v1/members/me/leave", headers=H).json == {
        "requiresApproval": False,
        "requestedAt": None,
    }
    resp = client.post("/api/v1/members/me/leave", headers=H)
    assert resp.status_code == 200 and resp.json["status"] == "left"

    anna = db.session.get(Member, club["anna"].id)
    assert anna.archived_at is not None
    assert db.session.query(UserTenant).filter_by(user_id=club["user"].id).count() == 0


def test_leaving_with_approval_waits_for_an_admin(client, db, club):
    _needs_approval(db, club["tenant"], True)
    _login(client, "anna@test.ch")
    resp = client.post("/api/v1/members/me/leave", headers=H)
    assert resp.json["status"] == "requested" and resp.json["requestedAt"]
    assert db.session.get(Member, club["anna"].id).archived_at is None

    # Withdrawn and asked again.
    assert (
        client.delete("/api/v1/members/me/leave", headers=H).json["requestedAt"] is None
    )
    client.post("/api/v1/members/me/leave", headers=H)

    _login(client, "admin@test.ch")
    pending = client.get("/api/v1/members/leave-requests", headers=H).json
    assert [p["id"] for p in pending] == [club["anna"].id]
    resp = client.post(f"/api/v1/members/{club['anna'].id}/leave/approve", headers=H)
    assert resp.status_code == 204
    assert db.session.get(Member, club["anna"].id).archived_at is not None
    assert client.get("/api/v1/members/leave-requests", headers=H).json == []


def test_admin_can_decline_a_request_to_leave(client, db, club):
    _needs_approval(db, club["tenant"], True)
    _login(client, "anna@test.ch")
    client.post("/api/v1/members/me/leave", headers=H)
    _login(client, "admin@test.ch")
    resp = client.post(f"/api/v1/members/{club['anna'].id}/leave/decline", headers=H)
    assert resp.status_code == 204
    anna = db.session.get(Member, club["anna"].id)
    assert anna.archived_at is None and anna.leave_requested_at is None


def test_members_cannot_approve_requests(client, db, club):
    _login(client, "anna@test.ch")
    assert client.get("/api/v1/members/leave-requests", headers=H).status_code == 403


def test_the_last_owner_cannot_leave(client, db, club, seeded_db):
    _login(client, "admin@test.ch")
    resp = client.post("/api/v1/members/me/leave", headers=H)
    assert resp.status_code == 409 and resp.json["error"] == "LAST_OWNER"


def test_a_former_member_can_ask_to_join_again(client, db, club):
    from hubra.core.models.application import Application

    _login(client, "anna@test.ch")
    client.post("/api/v1/members/me/leave", headers=H)
    from hubra.api.applications.services import ApplicationsService

    ApplicationsService.submit("Anna", "M", "anna@test.ch")
    db.session.commit()
    app_id = db.session.query(Application).one().id

    _login(client, "admin@test.ch")
    resp = client.post(f"/api/v1/applications/{app_id}/approve", json={}, headers=H)
    assert resp.status_code in (200, 201), resp.json
    anna = db.session.get(Member, club["anna"].id)
    assert anna.archived_at is None
    assert [r.name for r in anna.roles] == ["Member"]


def test_a_returning_member_gets_the_tier_and_mailbox_back(
    client, db, club, monkeypatch
):
    """Coming back used to keep the old tier, whatever was applied for, and
    left the club mailbox closed from when they left."""
    from hubra.api.applications.services import ApplicationsService
    from hubra.core.models.application import Application
    from hubra.core.models.member import MembershipTier
    from hubra.core.services import managed_mail

    reopened = []
    monkeypatch.setattr(
        managed_mail, "enable_member_mail", lambda mid, _hash: reopened.append(mid)
    )
    junior = MembershipTier(name="Junior", price_chf=10)
    db.session.add(junior)
    db.session.commit()

    _login(client, "anna@test.ch")
    client.post("/api/v1/members/me/leave", headers=H)
    ApplicationsService.submit("Anna", "M", "anna@test.ch", wants_tier_id=junior.id)
    db.session.commit()
    app_id = db.session.query(Application).one().id

    _login(client, "admin@test.ch")
    resp = client.post(f"/api/v1/applications/{app_id}/approve", json={}, headers=H)
    assert resp.status_code in (200, 201), resp.json
    anna = db.session.get(Member, club["anna"].id)
    assert anna.tier_id == junior.id
    assert reopened == [anna.id]
