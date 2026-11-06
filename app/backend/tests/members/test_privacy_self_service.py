"""revDSG self-service: a member's own data copy, deletion request,
consents with their history, and the club's retention rule
(hubra.core.services.privacy, data_requests.purge_former_members)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from hubra.core.models.consent import MemberConsent
from hubra.core.models.data_request import DataRequest
from hubra.core.models.member import Member
from hubra.core.models.tenant import Tenant
from hubra.core.models.user import User
from hubra.core.models.user_tenant import UserTenant

H = {"X-Tenant-Slug": "club-a"}


@pytest.fixture
def club(db, seeded_db):
    t = Tenant(name="Club A", slug="club-a", status="active", settings={})
    db.session.add(t)
    db.session.flush()
    db.session.add(UserTenant(user_id=seeded_db["user"].id, tenant_id=t.id, is_owner=True))
    db.session.commit()
    return t


@pytest.fixture
def anna(db, club):
    user = User(email="anna@test.ch", first_name="Anna", last_name="Muster")
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()
    member = Member(user_id=user.id, status="active")
    db.session.add(member)
    db.session.add(UserTenant(user_id=user.id, tenant_id=club.id))
    db.session.commit()
    return member


def _login(client, email="anna@test.ch"):
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "password123"}, headers=H
    )
    assert resp.status_code == 200, resp.get_json()


def test_photo_consent_starts_unasked_and_every_change_is_logged(client, db, anna):
    _login(client)
    page = client.get("/api/v1/members/me/privacy", headers=H).get_json()
    assert page["photo_consent"] is None and page["deletion_request"] is None
    assert page["retention_years"] is None and page["log"] == []

    for value in (True, True, False):
        resp = client.put("/api/v1/members/me/privacy", json={"photo_consent": value}, headers=H)
        assert resp.status_code == 200
    page = resp.get_json()
    assert page["photo_consent"] is False
    # The repeated "yes" changed nothing, so two entries.
    assert [e["value"] for e in page["log"]] == [False, True]
    assert all(e["kind"] == "photos" and e["source"] == "self" for e in page["log"])

    bad = client.put("/api/v1/members/me/privacy", json={"photo_consent": "yes"}, headers=H)
    assert bad.status_code == 422


def test_directory_choices_are_logged(client, db, anna):
    _login(client)
    client.put("/api/v1/members/me/directory", json={"shared": ["phone"]}, headers=H)
    client.put("/api/v1/members/me/directory", json={"shared": ["phone"]}, headers=H)
    rows = db.session.scalars(
        select(MemberConsent).where(MemberConsent.member_id == anna.id)
    ).all()
    assert [(r.kind, r.value) for r in rows] == [("directory", ["phone"])]


def test_own_data_download_is_recorded_as_a_done_export(client, db, club, anna):
    _login(client)
    client.put("/api/v1/members/me/privacy", json={"photo_consent": True}, headers=H)
    resp = client.get("/api/v1/members/me/privacy/export", headers=H)
    assert resp.status_code == 200
    assert "attachment" in resp.headers["Content-Disposition"]
    data = resp.get_json()
    assert data["club"]["slug"] == "club-a"
    assert data["member"]["id"] == anna.id and data["member"]["photo_consent"] is True
    assert data["account"]["email"] == "anna@test.ch"
    assert "password_hash" not in data["account"]
    assert data["related"]["member_consents"][0]["kind"] == "photos"

    req = db.session.scalar(select(DataRequest).where(DataRequest.member_id == anna.id))
    assert req.kind == "export" and req.status == "done"
    assert req.received_via == "self-service" and len(req.exports) == 1


def test_deletion_request_goes_into_the_platform_queue_once(client, db, club, anna):
    _login(client)
    resp = client.post(
        "/api/v1/members/me/privacy/deletion", json={"note": "Bitte alles"}, headers=H
    )
    assert resp.status_code == 201
    assert resp.get_json()["deletion_request"]["due_on"]
    again = client.post("/api/v1/members/me/privacy/deletion", json={}, headers=H)
    assert again.status_code == 409
    req = db.session.scalar(select(DataRequest).where(DataRequest.kind == "deletion"))
    assert req.status == "open" and req.tenant_id == club.id
    assert req.subject_name == "Anna Muster" and req.note == "Bitte alles"
    # The member is untouched until the platform handles the request.
    assert db.session.get(Member, anna.id).archived_at is None


def test_board_sees_the_consent_history(client, db, anna):
    _login(client)
    client.put("/api/v1/members/me/privacy", json={"photo_consent": True}, headers=H)
    _login(client, "admin@test.ch")
    body = client.get(f"/api/v1/members/{anna.id}/consents", headers=H).get_json()
    assert body["photo_consent"] is True
    assert body["log"][0]["changed_by"] == anna.id


def test_retention_setting_is_validated(client, db, club):
    _login(client, "admin@test.ch")
    for bad in (0, 31, "5", True):
        resp = client.patch(
            "/api/v1/admin/club-settings",
            json={"former_member_retention_years": bad},
            headers=H,
        )
        assert resp.status_code in (400, 422), (bad, resp.status_code)
    ok = client.patch(
        "/api/v1/admin/club-settings", json={"former_member_retention_years": 10}, headers=H
    )
    assert ok.status_code == 200, ok.get_json()
    db.session.refresh(club)
    assert club.settings["branding"]["former_member_retention_years"] == 10


def test_retention_deletes_only_members_who_left_long_enough_ago(db, club, app):
    from hubra.core.services.data_requests import purge_former_members

    now = datetime.now(timezone.utc)
    old = Member(status="former", archived_at=now - timedelta(days=365 * 5 + 2))
    recent = Member(status="former", archived_at=now - timedelta(days=200))
    active = Member(status="active")
    db.session.add_all([old, recent, active])
    db.session.commit()
    ids = (old.id, recent.id, active.id)

    result = purge_former_members(club, 5, now=now)
    assert result["deleted"] == 1 and result["skipped"] == 0
    left = set(db.session.scalars(select(Member.id).where(Member.id.in_(ids))).all())
    assert left == {recent.id, active.id}


def test_retention_job_does_nothing_without_the_setting(db, club, app):
    from hubra.core.services.privacy import retention_years

    assert retention_years(club) is None
    club.settings = {"branding": {"former_member_retention_years": 3}}
    assert retention_years(club) == 3
    club.settings = {"branding": {"former_member_retention_years": 99}}
    assert retention_years(club) is None
