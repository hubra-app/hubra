"""Calendar subscription feed and the iCalendar output."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from tests.helpers import set_modules
from hubra.api.events.services import EventService, _fold
from hubra.core.models.event import ClubEvent


@pytest.fixture
def events(db, seeded_db):
    soon = date.today() + timedelta(days=3)
    evs = [
        ClubEvent(
            title="Repair café, monthly",
            date=soon,
            time="14:00-18:00",
            type="Workshop",
            location="Hall; ground floor",
            description="Bring tools\nand snacks",
        ),
        ClubEvent(
            title="Camp",
            date=soon,
            end_date=soon + timedelta(days=2),
            type="Social",
            all_day=True,
        ),
        ClubEvent(title="Old", date=date.today() - timedelta(days=200), type="Meeting"),
    ]
    db.session.add_all(evs)
    db.session.commit()
    return evs


def _feed_path(client) -> str:
    url = client.get("/api/v1/events/calendar/feed").get_json()["url"]
    return url[url.index("/api/") :]


def test_feed_works_without_login(client, auth_headers, events):
    path = _feed_path(client)
    client.environ_base.pop("HTTP_AUTHORIZATION", None)
    resp = client.get(path, headers={"Authorization": ""})
    assert resp.status_code == 200
    assert resp.mimetype == "text/calendar"
    body = resp.get_data(as_text=True)
    assert body.count("BEGIN:VEVENT") == 2  # the 200-day-old event is left out
    assert "SUMMARY:Repair café\\, monthly" in body
    assert "LOCATION:Hall\; ground floor" in body
    assert "DESCRIPTION:Bring tools\\nand snacks" in body
    assert "T140000" in body and "T180000" in body
    camp_end = (events[1].end_date + timedelta(days=1)).strftime("%Y%m%d")
    assert f"DTEND;VALUE=DATE:{camp_end}" in body
    assert "DTSTAMP:" in body


def test_feed_rejects_tampered_token(client, auth_headers, events):
    path = _feed_path(client)
    assert client.get(path.replace(".ics", "x.ics")).status_code == 404


def test_feed_stops_when_member_archived_or_events_off(
    client, db, auth_headers, events, seeded_db
):
    path = _feed_path(client)
    set_modules(False, "events")
    assert client.get(path).status_code == 404
    set_modules(True, "events")
    seeded_db["admin"].archived_at = db.func.now()
    db.session.commit()
    assert client.get(path).status_code == 404


def test_feed_stops_when_member_disabled(client, db, auth_headers, events, seeded_db):
    path = _feed_path(client)
    seeded_db["admin"].is_disabled = True
    db.session.commit()
    assert client.get(path).status_code == 404


def test_long_lines_are_folded():
    line = "DESCRIPTION:" + "ä" * 60
    folded = _fold(line)
    assert all(len(part.encode()) <= 75 for part in folded.split("\r\n"))
    assert folded.replace("\r\n ", "") == line


def test_ical_without_events_is_valid():
    out = EventService.generate_ical([])
    assert out.startswith("BEGIN:VCALENDAR") and out.endswith("END:VCALENDAR\r\n")


def test_event_uids_name_the_club(app, tenant_pair):
    """Event ids repeat across clubs, so a UID without the club would make
    calendar apps merge club A's event 1 with club B's event 1."""
    from datetime import date

    from flask import g

    from hubra.api.events.services import EventService
    from hubra.core.models.event import ClubEvent

    event = ClubEvent(id=1, title="Meeting", date=date(2026, 5, 1), type="Social")
    uids = []
    for tenant in (tenant_pair["tenant_a"], tenant_pair["tenant_b"]):
        with app.test_request_context():
            g.tenant = tenant
            ical = EventService.generate_ical([event])
        uids += [line for line in ical.splitlines() if line.startswith("UID:")]
    assert uids == ["UID:event-1@tenant-a.hubra", "UID:event-1@tenant-b.hubra"]
