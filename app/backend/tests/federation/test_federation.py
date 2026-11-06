"""Federation view: an association, its member clubs and shared events
(hubra.core.services.federation).

The test database has one schema, so both clubs see the same rows; what
these tests check is who may see what, and when.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from hubra.core.models.event import ClubEvent
from hubra.core.models.federation import FederationLink
from hubra.core.models.function import Function, FunctionHolder
from hubra.core.models.member import Member
from hubra.core.models.tenant import Tenant
from hubra.core.models.user import User
from hubra.core.models.user_tenant import UserTenant
from tests.helpers import set_modules

FED = {"X-Tenant-Slug": "verband"}
CLUB = {"X-Tenant-Slug": "rc-uri"}


@pytest.fixture
def clubs(db, seeded_db):
    fed = Tenant(
        name="Ruderverband Zentralschweiz", slug="verband", status="active", settings={}
    )
    club = Tenant(name="Ruderclub Uri", slug="rc-uri", status="active", settings={})
    db.session.add_all([fed, club])
    db.session.flush()
    for t in (fed, club):
        db.session.add(
            UserTenant(user_id=seeded_db["user"].id, tenant_id=t.id, is_owner=True)
        )
    seeded_db["admin"].public_email = "praesident@rc-uri.ch"
    db.session.commit()
    return {"fed": fed, "club": club}


def _login(client, headers, email="admin@test.ch"):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.get_json()
    # The token's club wins over the header, so pick the club as the app does.
    resp = client.post(
        "/api/v1/auth/switch-tenant", json={"tenantSlug": headers["X-Tenant-Slug"]}
    )
    assert resp.status_code == 200, resp.get_json()


def _invite(client):
    _login(client, FED)
    resp = client.post(
        "/api/v1/app/federation/clubs", json={"slug": "RC-Uri"}, headers=FED
    )
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def test_invite_shares_nothing_until_the_club_accepts(client, db, clubs):
    row = _invite(client)
    assert row["status"] == "invited" and row["name"] == "Ruderclub Uri"
    assert row["members"] is None and row["contacts"] == []

    # Twice is refused, as is the association itself or an unknown club.
    again = client.post(
        "/api/v1/app/federation/clubs", json={"slug": "rc-uri"}, headers=FED
    )
    assert again.status_code == 409
    own = client.post(
        "/api/v1/app/federation/clubs", json={"slug": "verband"}, headers=FED
    )
    assert own.status_code == 400
    unknown = client.post(
        "/api/v1/app/federation/clubs", json={"slug": "nope"}, headers=FED
    )
    assert unknown.status_code == 404

    # The club sees the invitation in its settings.
    _login(client, CLUB)
    body = client.get("/api/v1/app/settings/associations", headers=CLUB).get_json()
    assert [(a["name"], a["status"]) for a in body["associations"]] == [
        ("Ruderverband Zentralschweiz", "invited")
    ]


def test_accepted_club_shows_its_count_and_contacts_only_when_shared(
    client, db, seeded_db, clubs
):
    row = _invite(client)
    function = Function(name="Präsidium", mailbox_ref=None)
    db.session.add(function)
    db.session.flush()
    db.session.add(
        FunctionHolder(function_id=function.id, member_id=seeded_db["admin"].id)
    )
    db.session.commit()

    _login(client, CLUB)
    resp = client.post(
        f"/api/v1/app/settings/associations/{row['id']}/accept", json={}, headers=CLUB
    )
    assert resp.status_code == 200
    assert (
        resp.get_json()["status"] == "active"
        and resp.get_json()["shareContacts"] is False
    )

    _login(client, FED)
    club = client.get("/api/v1/app/federation/clubs", headers=FED).get_json()["clubs"][
        0
    ]
    assert club["status"] == "active"
    assert club["members"] == 1
    assert club["contacts"] == []

    _login(client, CLUB)
    resp = client.patch(
        f"/api/v1/app/settings/associations/{row['id']}",
        json={"shareContacts": True},
        headers=CLUB,
    )
    assert resp.status_code == 200

    _login(client, FED)
    club = client.get("/api/v1/app/federation/clubs", headers=FED).get_json()["clubs"][
        0
    ]
    # The holder's club address, never the private sign-in address.
    assert club["contacts"] == [
        {"function": "Präsidium", "name": "Test Admin", "email": "praesident@rc-uri.ch"}
    ]


def test_shared_events_reach_member_clubs_only(client, db, clubs):
    soon = date.today() + timedelta(days=3)
    db.session.add_all(
        [
            ClubEvent(
                title="Regionalregatta",
                date=soon,
                type="Social",
                federation_shared=True,
            ),
            ClubEvent(title="Vorstandssitzung", date=soon, type="Meeting"),
            ClubEvent(
                title="Vergangen",
                date=date.today() - timedelta(days=9),
                type="Social",
                federation_shared=True,
            ),
        ]
    )
    db.session.commit()
    row = _invite(client)

    _login(client, CLUB)
    # Not yet a member: nothing.
    body = client.get("/api/v1/app/events/from-associations", headers=CLUB).get_json()
    assert body["events"] == []

    client.post(
        f"/api/v1/app/settings/associations/{row['id']}/accept", json={}, headers=CLUB
    )
    body = client.get("/api/v1/app/events/from-associations", headers=CLUB).get_json()
    assert [(e["title"], e["federation"]) for e in body["events"]] == [
        ("Regionalregatta", "Ruderverband Zentralschweiz")
    ]

    # The association turns the module off: its events stop showing.
    set_modules(False, "federation")
    body = client.get("/api/v1/app/events/from-associations", headers=CLUB).get_json()
    assert body["events"] == []


def test_event_form_round_trips_the_flag(client, db, clubs):
    _login(client, FED)
    resp = client.post(
        "/api/v1/app/events/",
        json={
            "title": "Verbandstag",
            "date": (date.today() + timedelta(days=10)).isoformat(),
            "type": "Meeting",
            "federation_shared": True,
        },
        headers=FED,
    )
    assert resp.status_code == 201, resp.get_json()
    assert resp.get_json()["federation_shared"] is True
    event = db.session.get(ClubEvent, resp.get_json()["id"])
    assert event.federation_shared is True


def test_only_admins_answer_and_only_their_own_links(client, db, clubs):
    row = _invite(client)
    user = User(email="anna@test.ch", first_name="Anna", last_name="Muster")
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()
    db.session.add(Member(user_id=user.id, status="active"))
    db.session.add(UserTenant(user_id=user.id, tenant_id=clubs["club"].id))
    db.session.commit()

    _login(client, CLUB, email="anna@test.ch")
    resp = client.post(
        f"/api/v1/app/settings/associations/{row['id']}/accept", json={}, headers=CLUB
    )
    assert resp.status_code == 403
    assert client.get("/api/v1/app/federation/clubs", headers=CLUB).status_code == 403

    # The association can't answer for the club: the link isn't its own there.
    _login(client, FED)
    resp = client.post(
        f"/api/v1/app/settings/associations/{row['id']}/accept", json={}, headers=FED
    )
    assert resp.status_code == 404
    assert db.session.get(FederationLink, row["id"]).status == "invited"


def test_leaving_and_removing(client, db, clubs):
    row = _invite(client)
    _login(client, CLUB)
    client.post(
        f"/api/v1/app/settings/associations/{row['id']}/accept", json={}, headers=CLUB
    )
    assert (
        client.delete(
            f"/api/v1/app/settings/associations/{row['id']}", headers=CLUB
        ).status_code
        == 204
    )
    assert db.session.get(FederationLink, row["id"]) is None

    row = _invite(client)
    assert (
        client.delete(
            f"/api/v1/app/federation/clubs/{row['id']}", headers=FED
        ).status_code
        == 204
    )
    _login(client, CLUB)
    assert (
        client.get("/api/v1/app/settings/associations", headers=CLUB).get_json()[
            "associations"
        ]
        == []
    )
