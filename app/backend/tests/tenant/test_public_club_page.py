"""A club's public page on the join portal and the events widget for the
club's own website (hubra.api.tenant.public_page)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from hubra.core.models.event import ClubEvent
from hubra.core.models.group import Group
from hubra.core.models.tenant import Tenant


@pytest.fixture
def club(db, seeded_db):
    tenant = Tenant(
        name="Ruderclub Uri",
        slug="rc-uri",
        status="active",
        settings={"branding": {"club_description": "Rudern auf dem Urnersee."}},
    )
    db.session.add(tenant)
    soon = date.today() + timedelta(days=4)
    db.session.add_all(
        [
            ClubEvent(title="Tag der offenen Tür", date=soon, type="Social", is_public=True),
            ClubEvent(title="Vorstandssitzung", date=soon, type="Meeting"),
            ClubEvent(title="Schnuppertraining", date=soon, type="Training", trial_spots=4),
            Group(name="Junioren", description="Mittwoch 18 Uhr", visibility="open"),
            Group(name="Vorstand intern", visibility="private"),
        ]
    )
    db.session.commit()
    return tenant


def _url(club):
    return f"/api/v1/global/clubs/{club.slug}/public"


def _set(db, club, **values):
    branding = dict((club.settings or {}).get("branding", {}))
    branding.update(values)
    club.settings = {**(club.settings or {}), "branding": branding}
    db.session.commit()


def test_off_until_the_club_turns_it_on(client, club):
    resp = client.get(_url(club))
    assert resp.status_code == 404


def test_shows_public_events_only_and_no_groups_by_default(client, db, club):
    _set(db, club, public_page=True, website="https://rc-uri.ch")
    body = client.get(_url(club)).get_json()
    assert body["name"] == "Ruderclub Uri"
    assert body["description"] == "Rudern auf dem Urnersee."
    assert body["website"] == "https://rc-uri.ch"
    assert [e["title"] for e in body["events"]] == ["Tag der offenen Tür"]
    assert all(e["url"] is None for e in body["events"])
    assert body["groups"] == [] and body["trials"] is True
    assert body["acceptsRequests"] is True


def test_groups_only_when_listed_publicly_and_never_private(client, db, club):
    _set(db, club, public_page=True, public_group_listing=True)
    body = client.get(_url(club)).get_json()
    assert [g["name"] for g in body["groups"]] == ["Junioren"]
    assert body["groups"][0]["description"] == "Mittwoch 18 Uhr"


def test_no_member_data_on_the_page(client, db, club):
    _set(db, club, public_page=True, public_group_listing=True)
    text = client.get(_url(club)).get_data(as_text=True)
    assert "@" not in text.replace("https://", "")


def test_settings_validate_the_website(client, db, club):
    from hubra.core.schemas.club_settings import ClubSettingsSchema
    from marshmallow import ValidationError

    schema = ClubSettingsSchema()
    assert schema.load({"public_page": True, "website": "https://x.ch"})["public_page"]
    with pytest.raises(ValidationError):
        schema.load({"website": "javascript:alert(1)"})


def test_widget_script_is_served_for_any_site(client, club):
    resp = client.get(f"/api/v1/events/public/{club.slug}/widget.js")
    assert resp.status_code == 200
    assert resp.mimetype == "application/javascript"
    assert resp.headers["Access-Control-Allow-Origin"] == "*"
    js = resp.get_data(as_text=True)
    assert "attachShadow" in js and "innerHTML" not in js
