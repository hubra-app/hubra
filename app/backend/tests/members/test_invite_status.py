"""The club sees the invites it sent, and an invite whose link got lost on the
way (signed up, then confirmed the address in another tab or on the phone)
can still be accepted from the club picker.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from hubra.core.models.club_invite import ClubInvite
from hubra.core.models.tenant import Tenant
from hubra.core.models.user import User

from tests.members import test_invites as base
from tests.members.test_invites import H, _invite, _member_of, _person


@pytest.fixture
def club(db, seeded_db):
    return base.club.__wrapped__(db, seeded_db)


@pytest.fixture
def admin(client, club):
    return base.admin.__wrapped__(client, club)


def _verify(db, email: str) -> None:
    user = db.session.scalar(select(User).where(User.email == email))
    user.private_email_verified = True
    db.session.commit()


def test_club_lists_its_invites_with_status(app, db, admin, club):
    _invite(admin, {"email": "open@test.ch"})
    token = _invite(admin, {"email": "joined@test.ch"})
    _invite(admin, {"email": "old@test.ch"})
    old = db.session.scalar(select(ClubInvite).where(ClubInvite.email == "old@test.ch"))
    old.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.session.commit()
    person = _person(app, "joined@test.ch")
    assert (
        person.post("/api/v1/system/invites/accept", json={"token": token}).status_code
        == 200
    )

    resp = admin.get("/api/v1/members/invites", headers=H)
    assert resp.status_code == 200
    status = {i["email"]: i["status"] for i in resp.get_json()}
    assert status == {
        "open@test.ch": "open",
        "joined@test.ch": "accepted",
        "old@test.ch": "expired",
    }
    assert all(i["invitedBy"] for i in resp.get_json())


def test_club_sees_only_its_own_invites(app, db, admin, club):
    _invite(admin, {"email": "mine@test.ch"})
    other = Tenant(name="Club B", slug="club-b", status="active", settings={})
    db.session.add(other)
    db.session.flush()
    db.session.add(
        ClubInvite(
            tenant_id=other.id,
            email="theirs@test.ch",
            token_hash="x" * 64,
            expires_at=datetime.now(timezone.utc) + timedelta(days=3),
        )
    )
    db.session.commit()
    theirs = db.session.scalar(
        select(ClubInvite).where(ClubInvite.email == "theirs@test.ch")
    )

    emails = [
        i["email"] for i in admin.get("/api/v1/members/invites", headers=H).get_json()
    ]
    assert emails == ["mine@test.ch"]
    assert (
        admin.delete(f"/api/v1/members/invites/{theirs.id}", headers=H).status_code
        == 404
    )
    assert (
        admin.post(f"/api/v1/members/invites/{theirs.id}/resend", headers=H).status_code
        == 404
    )


def test_resend_replaces_the_link_and_revoke_ends_it(app, db, admin, club):
    old_token = _invite(admin, {"email": "again@test.ch"})
    invite = db.session.scalar(
        select(ClubInvite).where(ClubInvite.email == "again@test.ch")
    )

    from unittest.mock import patch

    with patch("hubra.core.services.email._send") as send:
        resp = admin.post(f"/api/v1/members/invites/{invite.id}/resend", headers=H)
    assert resp.status_code == 200
    assert send.call_count == 1
    fresh_id = resp.get_json()["id"]

    person = _person(app, "again@test.ch")
    assert (
        person.post(
            "/api/v1/system/invites/lookup", json={"token": old_token}
        ).status_code
        == 404
    )

    assert (
        admin.delete(f"/api/v1/members/invites/{fresh_id}", headers=H).status_code
        == 204
    )
    assert admin.get("/api/v1/members/invites", headers=H).get_json() == []


def test_lost_link_accepted_from_the_club_picker(app, db, admin, club):
    _invite(admin, {"email": "lost@test.ch"})
    person = _person(app, "lost@test.ch")

    # Not confirmed yet: the address proves nothing, so nothing shows.
    assert person.get("/api/v1/system/invites/mine").get_json() == {"invites": []}

    _verify(db, "lost@test.ch")
    invites = person.get("/api/v1/system/invites/mine").get_json()["invites"]
    assert [(i["club"]["slug"], bool(i["invitedBy"])) for i in invites] == [
        ("club-a", True)
    ]

    resp = person.post(f"/api/v1/system/invites/{invites[0]['id']}/accept")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "joined"
    assert _member_of(db, "lost@test.ch") is not None
    assert person.get("/api/v1/system/invites/mine").get_json() == {"invites": []}


def test_cannot_accept_someone_elses_invite_by_id(app, db, admin, club):
    _invite(admin, {"email": "target@test.ch"})
    invite = db.session.scalar(
        select(ClubInvite).where(ClubInvite.email == "target@test.ch")
    )
    other = _person(app, "other@test.ch")
    _verify(db, "other@test.ch")
    assert other.post(f"/api/v1/system/invites/{invite.id}/accept").status_code == 404
    assert _member_of(db, "other@test.ch") is None
