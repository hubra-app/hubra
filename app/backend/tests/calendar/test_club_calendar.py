"""The club calendar: every module's dated items side by side, through
``<module>.calendar.items`` (roadmap idea 20)."""

from __future__ import annotations

import pytest

from hubra.core.contracts.calendar import calendar_contract
from hubra.core.extensions import db
from hubra.core.modules import Module, registry
from tests.events.test_m5_events import _create_event
from tests.helpers import set_modules
from tests.settings.test_settings_kv import _login, _make_role_and_member

URL = "/api/v1/app/calendar/"
JUNE = {"start": "2030-06-01", "end": "2030-06-30"}


def rooms(ctx, data):
    return {
        "items": [
            {
                "id": "booking:1",
                "title": "Werkstatt",
                "kind": "booking",
                "start": f"{data.start.isoformat()}T09:00:00",
                "end": f"{data.start.isoformat()}T11:00:00",
            }
        ]
    }


def broken(ctx, data):
    raise RuntimeError("down")


@pytest.fixture
def rooms_module(app, seeded_db):
    """A module offering calendar items, like the Booking plugin."""
    registry.load()
    registry._modules["rooms"] = Module(
        code="rooms",
        name="Rooms",
        provides=(calendar_contract("rooms", f"{__name__}:rooms"),),
    )
    registry._modules["flaky"] = Module(
        code="flaky",
        name="Flaky",
        provides=(calendar_contract("flaky", f"{__name__}:broken"),),
    )
    set_modules(True, "rooms", "flaky")
    yield
    registry._modules.pop("rooms", None)
    registry._modules.pop("flaky", None)


def test_events_and_other_modules_side_by_side(client, auth_headers, rooms_module):
    _create_event(
        client, auth_headers, title="Training", date="2030-06-06", time="18:30-20:00"
    )
    _create_event(client, auth_headers, title="Später", date="2030-08-01")
    resp = client.get(URL, query_string=JUNE, headers=auth_headers)
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body["sources"] == ["events", "rooms"]
    assert body["failed"] == ["flaky"]
    by_title = {i["title"]: i for i in body["items"]}
    assert "Später" not in by_title
    training = by_title["Training"]
    assert training["source"] == "events" and training["kind"] == "event"
    assert training["start"] == "2030-06-06T18:30:00"
    assert training["end"] == "2030-06-06T20:00:00"
    assert training["all_day"] is False
    assert "event=" in training["path"]
    assert by_title["Werkstatt"]["source"] == "rooms"
    # Sorted by start.
    assert [i["title"] for i in body["items"]] == ["Werkstatt", "Training"]


def test_an_all_day_event_spans_its_days(client, auth_headers, seeded_db):
    _create_event(
        client, auth_headers, title="Lager", date="2030-06-10", end_date="2030-06-12"
    )
    items = client.get(URL, query_string=JUNE, headers=auth_headers).get_json()["items"]
    lager = next(i for i in items if i["title"] == "Lager")
    assert lager["all_day"] is True
    assert lager["start"] == "2030-06-10T00:00:00"
    assert lager["end"] == "2030-06-12T00:00:00"


def test_a_member_without_the_right_sees_no_events(
    client, app, seeded_db, auth_headers
):
    _create_event(client, auth_headers, title="Training", date="2030-06-06")
    app.test_cli_runner().invoke(args=["sync-permissions"])
    _make_role_and_member(
        db, seeded_db["tier"], name="Reader", permission_keys=["posts.posts.read"]
    )
    client.post("/api/v1/auth/logout")
    _login(client, "reader@test.ch")
    body = client.get(URL, query_string=JUNE).get_json()
    assert "events" not in body["sources"]
    assert body["items"] == []


def test_signed_out_and_bad_ranges(client, auth_headers, seeded_db):
    bad = [
        {},
        {"start": "2030-06-30", "end": "2030-06-01"},
        {"start": "2030-01-01", "end": "2031-12-31"},
        {"start": "june", "end": "2030-06-30"},
    ]
    for q in bad:
        assert client.get(URL, query_string=q, headers=auth_headers).status_code == 400
    client.post("/api/v1/auth/logout")
    assert client.get(URL, query_string=JUNE).status_code == 401
