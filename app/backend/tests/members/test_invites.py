"""A club adds people only by invite; the person accepts with their own account.

SQLite has no schemas, so the club here shares the one members table.
"""

from __future__ import annotations

import io
import re
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select

from hubra.core.models.application import Application
from hubra.core.models.club_invite import ClubInvite
from hubra.core.models.member import Member
from hubra.core.models.role import Role
from hubra.core.models.tenant import Tenant
from hubra.core.models.user import User
from hubra.core.models.user_tenant import UserTenant

H = {"X-Tenant-Slug": "club-a"}
PASSWORD = "VeryStrongPass123!"


@pytest.fixture
def club(db, seeded_db):
    tenant = Tenant(name="Club A", slug="club-a", status="active", settings={})
    db.session.add(tenant)
    db.session.flush()
    # New members get the club's default role, not Admin.
    seeded_db["role"].is_default = False
    member_role = Role(name="Member", is_default=True)
    db.session.add(member_role)
    db.session.add(
        UserTenant(user_id=seeded_db["user"].id, tenant_id=tenant.id, is_owner=True)
    )
    db.session.commit()
    return {"tenant": tenant, "member_role": member_role}


@pytest.fixture
def admin(client, club):
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
        headers=H,
    )
    return client


def _invite(admin, payload) -> str:
    """Invite through the club; returns the raw token from the mail."""
    with patch("hubra.core.services.email._send") as send:
        resp = admin.post("/api/v1/members/", json=payload, headers=H)
    assert resp.status_code == 202, resp.get_json()
    assert resp.get_json() == {"invited": True, "email": payload["email"]}
    to_email, _name, _subject, _html, body_text = send.call_args.args[:5]
    assert to_email == payload["email"]
    return re.search(r"/invite#token=([\w-]+)", body_text).group(1)


def _person(app, email: str, *, signup: bool = True):
    """A separate browser for the invited person, signed up and signed in."""
    c = app.test_client()
    if signup:
        resp = c.post(
            "/api/v1/auth/signup",
            json={"name": "Ines Invited", "email": email, "password": PASSWORD},
        )
        assert resp.status_code == 201
    return c


def _member_of(db, email: str) -> Member | None:
    return db.session.scalar(
        select(Member).join(User, Member.user_id == User.id).where(User.email == email)
    )


def test_inviting_creates_no_account_and_no_member(db, admin, club, seeded_db):
    _invite(
        admin,
        {"email": "new@test.ch", "first_name": "Ines", "tier_id": seeded_db["tier"].id},
    )
    assert db.session.scalar(select(User).where(User.email == "new@test.ch")) is None
    invite = db.session.scalar(select(ClubInvite))
    assert invite.tenant_id == club["tenant"].id
    assert invite.email == "new@test.ch"
    assert invite.member_data["tier_id"] == seeded_db["tier"].id


def test_new_person_signs_up_and_accepts(app, db, admin, club, seeded_db):
    token = _invite(admin, {"email": "new@test.ch", "tier_id": seeded_db["tier"].id})
    person = _person(app, "new@test.ch")

    resp = person.post("/api/v1/system/invites/lookup", json={"token": token})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["club"] == {"slug": "club-a", "name": "Club A"}
    assert body["emailMatches"] is True
    assert body["membership"] is None

    resp = person.post("/api/v1/system/invites/accept", json={"token": token})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "joined"

    member = _member_of(db, "new@test.ch")
    assert member is not None
    assert member.tier_id == seeded_db["tier"].id
    assert [r.name for r in member.roles] == ["Member"]
    assert db.session.scalar(
        select(UserTenant).where(
            UserTenant.user_id == member.user_id,
            UserTenant.tenant_id == club["tenant"].id,
        )
    )
    # The link is used up.
    resp = person.post("/api/v1/system/invites/accept", json={"token": token})
    assert resp.status_code == 404


def test_existing_account_keeps_its_password(app, db, admin, club):
    person = _person(app, "known@test.ch")
    token = _invite(admin, {"email": "known@test.ch"})
    resp = person.post("/api/v1/system/invites/accept", json={"token": token})
    assert resp.status_code == 200
    user = db.session.scalar(select(User).where(User.email == "known@test.ch"))
    assert user.check_password(PASSWORD)


def test_only_the_invited_address_can_accept(app, db, admin, club):
    token = _invite(admin, {"email": "invited@test.ch"})
    other = _person(app, "someone-else@test.ch")
    assert (
        other.post("/api/v1/system/invites/lookup", json={"token": token}).get_json()[
            "emailMatches"
        ]
        is False
    )
    resp = other.post("/api/v1/system/invites/accept", json={"token": token})
    assert resp.status_code == 403
    assert _member_of(db, "someone-else@test.ch") is None


def test_accepting_needs_a_sign_in(app, admin, club):
    token = _invite(admin, {"email": "anon@test.ch"})
    anon = _person(app, "anon@test.ch", signup=False)
    resp = anon.post("/api/v1/system/invites/accept", json={"token": token})
    assert resp.status_code == 401


def test_expired_or_unknown_links_are_refused(app, db, admin, club):
    token = _invite(admin, {"email": "late@test.ch"})
    invite = db.session.scalar(select(ClubInvite))
    invite.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.session.commit()
    person = _person(app, "late@test.ch")
    for t in (token, "not-a-token"):
        resp = person.post("/api/v1/system/invites/accept", json={"token": t})
        assert resp.status_code == 404
    assert _member_of(db, "late@test.ch") is None


def test_a_new_invite_replaces_the_old_link(app, admin, club):
    first = _invite(admin, {"email": "twice@test.ch"})
    second = _invite(admin, {"email": "twice@test.ch"})
    person = _person(app, "twice@test.ch")
    assert (
        person.post("/api/v1/system/invites/accept", json={"token": first}).status_code
        == 404
    )
    assert (
        person.post("/api/v1/system/invites/accept", json={"token": second}).status_code
        == 200
    )


def test_inviting_a_member_is_a_conflict(admin, club):
    resp = admin.post("/api/v1/members/", json={"email": "admin@test.ch"}, headers=H)
    assert resp.status_code == 409


def test_import_invites_everyone_new(db, admin, club):
    csv_data = (
        "first_name,last_name,email\n"
        "Alice,Smith,alice@test.ch\n"
        "Already,Here,admin@test.ch\n"
        "No,Mail,\n"
    )
    with patch("hubra.core.services.email._send") as send:
        resp = admin.post(
            "/api/v1/members/import",
            data={"file": (io.BytesIO(csv_data.encode()), "members.csv")},
            content_type="multipart/form-data",
            headers=H,
        )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["invited"] == 1
    assert body["skipped"] == 1
    assert len(body["errors"]) == 1
    assert send.call_count == 1
    assert db.session.scalar(select(User).where(User.email == "alice@test.ch")) is None


def test_approving_an_application_without_an_account_invites(db, admin, club):
    application = Application(name="Paula Paper", email="paper@test.ch")
    db.session.add(application)
    db.session.commit()
    with patch("hubra.core.services.email._send"):
        resp = admin.post(f"/api/v1/applications/{application.id}/approve", headers=H)
    assert resp.status_code == 202
    assert db.session.scalar(select(User).where(User.email == "paper@test.ch")) is None
    assert db.session.scalar(select(ClubInvite)).email == "paper@test.ch"
    assert db.session.scalar(select(Application)) is None
