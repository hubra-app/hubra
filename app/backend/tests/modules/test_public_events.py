"""A club's public events: JSON for its website and a calendar, no sign-in."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from hubra.core.models.event import ClubEvent


@pytest.fixture
def club(db):
    from hubra.core.models.tenant import Tenant

    tenant = Tenant(name="Open Club", slug="open-club", plan="starter", status="active")
    db.session.add(tenant)
    db.session.commit()
    yield tenant
    db.session.delete(tenant)
    db.session.commit()


@pytest.fixture
def events(db, seeded_db, club):
    soon = date.today() + timedelta(days=3)
    evs = [
        ClubEvent(
            title="Open day", date=soon, type="Social", is_public=True, location="Hall"
        ),
        ClubEvent(title="Board meeting", date=soon, type="Meeting"),
        ClubEvent(
            title="Last month's fair",
            date=date.today() - timedelta(days=10),
            type="Social",
            is_public=True,
        ),
    ]
    db.session.add_all(evs)
    db.session.commit()
    return evs


def _links(client, club):
    from unittest.mock import patch

    with patch("hubra.core.tenant.context.current_tenant", return_value=club):
        links = client.get("/api/v1/events/public-links").get_json()
    return {
        k: v[v.index("/api/") :] for k, v in links.items() if isinstance(v, str)
    }, links


def test_public_events_without_login(client, auth_headers, events, club):
    paths, links = _links(client, club)
    assert links["upcoming"] == 1
    client.environ_base.pop("HTTP_AUTHORIZATION", None)
    resp = client.get(paths["json"], headers={"Authorization": ""})
    assert resp.status_code == 200
    assert resp.headers["Access-Control-Allow-Origin"] == "*"
    body = resp.get_json()
    # Upcoming public ones only: no members-only event, nothing past.
    assert [e["title"] for e in body["events"]] == ["Open day"]
    assert body["events"][0]["location"] == "Hall"
    assert "attendees" not in body["events"][0]


def test_public_calendar(client, auth_headers, events, club):
    paths, _ = _links(client, club)
    client.environ_base.pop("HTTP_AUTHORIZATION", None)
    resp = client.get(paths["calendar"], headers={"Authorization": ""})
    assert resp.status_code == 200 and resp.mimetype == "text/calendar"
    body = resp.get_data(as_text=True)
    assert "SUMMARY:Open day" in body and "SUMMARY:Last month's fair" in body
    assert "Board meeting" not in body


def test_unknown_club(client, auth_headers, events):
    assert client.get("/api/v1/events/public/no-such-club").status_code == 404
    assert client.get("/api/v1/events/public/no-such-club.ics").status_code == 404
