"""Clubs suggest texts; platform admins accept or reject them."""

import pytest

from hubra.core.models.tenant import Tenant
from hubra.core.models.translation import Translation

CLUB = {"X-Tenant-Slug": "club-a"}
PLATFORM = "/api/v1/manager/platform/translation-requests"


@pytest.fixture
def club(client, db, seeded_db):
    db.session.add(Tenant(name="Club A", slug="club-a", status="active"))
    db.session.add(Translation(locale="de-CH", key="common.save", value="Speichern"))
    db.session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.ch", "password": "password123"},
        headers=CLUB,
    )
    return seeded_db


def _suggest(client, **body):
    payload = {"locale": "de-CH", "key": "common.save", "value": "Sichern"} | body
    return client.post("/api/v1/i18n/requests", json=payload, headers=CLUB)


def test_a_club_suggests_and_sees_its_suggestions(client, club):
    resp = _suggest(client, note="Kürzer")
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    assert body["currentValue"] == "Speichern"
    assert body["proposedValue"] == "Sichern"
    assert body["status"] == "pending"

    listed = client.get("/api/v1/i18n/requests", headers=CLUB).get_json()
    assert [r["key"] for r in listed] == ["common.save"]


def test_a_suggestion_must_change_the_text(client, club):
    assert _suggest(client, value="Speichern").status_code == 400
    assert _suggest(client, value="  ").status_code == 400


def test_a_club_admin_cannot_decide(client, club):
    req = _suggest(client).get_json()
    resp = client.post(f"{PLATFORM}/{req['id']}", json={"accept": True})
    assert resp.status_code == 403


def test_accepting_changes_the_text_for_every_club(client, club, db):
    req = _suggest(client).get_json()
    club["user"].is_superadmin = True
    db.session.commit()

    pending = client.get(f"{PLATFORM}?status=pending").get_json()
    assert [(r["key"], r["tenantName"]) for r in pending] == [("common.save", "Club A")]

    resp = client.post(f"{PLATFORM}/{req['id']}", json={"accept": True, "value": "Sichern!"})
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["status"] == "accepted"
    row = db.session.query(Translation).filter_by(locale="de-CH", key="common.save").one()
    assert row.value == "Sichern!"

    again = client.post(f"{PLATFORM}/{req['id']}", json={"accept": False})
    assert again.status_code == 409


def test_rejecting_keeps_the_text_and_tells_the_club_why(client, club, db):
    req = _suggest(client).get_json()
    club["user"].is_superadmin = True
    db.session.commit()

    resp = client.post(f"{PLATFORM}/{req['id']}", json={"accept": False, "note": "Bleibt"})
    assert resp.status_code == 200
    row = db.session.query(Translation).filter_by(locale="de-CH", key="common.save").one()
    assert row.value == "Speichern"
    listed = client.get("/api/v1/i18n/requests", headers=CLUB).get_json()
    assert (listed[0]["status"], listed[0]["decisionNote"]) == ("rejected", "Bleibt")
