"""Open invitations: the club sees, resends and withdraws invites nobody accepted."""

from datetime import UTC
from unittest.mock import patch

import pytest

from hubra.core.models.club_invite import ClubInvite
from hubra.core.models.tenant import Tenant


@pytest.fixture
def club(db, seeded_db):
    tenant = Tenant(name="Invite Club", slug="invite-club", plan="starter")
    db.session.add(tenant)
    db.session.commit()
    with (
        patch("hubra.core.tenant.context.current_tenant", return_value=tenant),
        patch("hubra.core.services.email.send_club_invite") as sent,
    ):
        yield tenant, sent


@pytest.fixture
def admin(client, seeded_db):
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
    )


def _invite(client, email="new@test.ch"):
    resp = client.post("/api/v1/members/", json={"email": email, "status": "trial"})
    assert resp.status_code == 202, resp.get_json()


def test_list_resend_and_cancel(club, admin, client, db):
    tenant, sent = club
    _invite(client)

    body = client.get("/api/v1/members/invites").get_json()
    assert [i["email"] for i in body["invites"]] == ["new@test.ch"]
    first = body["invites"][0]
    assert first["expired"] is False

    old_hash = db.session.get(ClubInvite, first["id"]).token_hash
    resp = client.post(f"/api/v1/members/invites/{first['id']}/resend")
    assert resp.status_code == 200
    assert sent.call_count == 2
    # A fresh link replaces the old one: still one open invite.
    invites = client.get("/api/v1/members/invites").get_json()["invites"]
    assert len(invites) == 1
    db.session.expire_all()
    assert db.session.get(ClubInvite, invites[0]["id"]).token_hash != old_hash

    assert client.delete(f"/api/v1/members/invites/{invites[0]['id']}").status_code == 204
    assert client.get("/api/v1/members/invites").get_json()["invites"] == []
    assert db.session.query(ClubInvite).filter_by(tenant_id=tenant.id).count() == 0


def test_another_clubs_invite_is_not_found(club, admin, client, db):
    other = Tenant(name="Other", slug="other-club", plan="starter")
    db.session.add(other)
    db.session.flush()
    from datetime import datetime, timedelta

    invite = ClubInvite(
        tenant_id=other.id,
        email="x@test.ch",
        token_hash="f" * 64,
        expires_at=datetime.now(UTC) + timedelta(days=3),
    )
    db.session.add(invite)
    db.session.commit()

    assert client.get("/api/v1/members/invites").get_json()["invites"] == []
    assert client.post(f"/api/v1/members/invites/{invite.id}/resend").status_code == 404
    assert client.delete(f"/api/v1/members/invites/{invite.id}").status_code == 404
