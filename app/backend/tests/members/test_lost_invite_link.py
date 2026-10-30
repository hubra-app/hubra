"""An invite whose link got lost on the
way (signed up, then confirmed the address in another tab or on the phone)
can still be accepted from the club picker.
"""

from __future__ import annotations


import pytest
from sqlalchemy import select

from hubra.core.models.club_invite import ClubInvite
from hubra.core.models.user import User

from tests.members import test_invites as base
from tests.members.test_invites import _invite, _member_of, _person


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
