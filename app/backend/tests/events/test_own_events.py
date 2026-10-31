"""Whoever put an event up runs it, without the club-wide event rights:
they edit and cancel it and handle its sign-ups. Other events stay closed."""

from datetime import date, timedelta

import pytest

from tests.settings.test_settings_kv import _login, _make_role_and_member

_HOST = ["events.events.read", "events.events.create", "events.events.register"]
_SOON = (date.today() + timedelta(days=5)).isoformat()


@pytest.fixture
def host(client, app, db, seeded_db):
    app.test_cli_runner().invoke(args=["sync-permissions"])
    tier = seeded_db["tier"]
    _make_role_and_member(db, tier, name="Hanna", permission_keys=_HOST)
    guest = _make_role_and_member(
        db, tier, name="Gert", permission_keys=["events.events.read", "events.events.register"]
    )
    _login(client, "admin@test.ch")
    theirs = client.post(
        "/api/v1/events/", json={"title": "Club night", "date": _SOON, "type": "Social"}
    ).get_json()["id"]
    _login(client, "hanna@test.ch")
    mine = client.post(
        "/api/v1/events/",
        json={"title": "Hike", "date": _SOON, "type": "Social", "requires_approval": True},
    ).get_json()["id"]
    return {"mine": mine, "theirs": theirs, "guest": guest}


def test_the_host_edits_their_own_event_only(client, host):
    _login(client, "hanna@test.ch")
    r = client.patch(f"/api/v1/events/{host['mine']}", json={"location": "Station"})
    assert r.status_code == 200 and r.get_json()["location"] == "Station"
    r = client.patch(f"/api/v1/events/{host['theirs']}", json={"location": "Mine"})
    assert r.status_code == 403
    assert client.delete(f"/api/v1/events/{host['theirs']}").status_code == 403


def test_the_host_handles_sign_ups(client, host):
    _login(client, "gert@test.ch")
    assert client.post(f"/api/v1/events/{host['mine']}/register", json={}).status_code == 201
    # A guest can't approve themselves.
    gid = host["guest"].id
    url = f"/api/v1/events/{host['mine']}/registrations/{gid}/approve"
    assert client.post(url).status_code == 403
    _login(client, "hanna@test.ch")
    assert client.get(f"/api/v1/events/{host['mine']}/registrations").status_code == 200
    assert client.post(url).status_code == 200
    assert client.post(f"/api/v1/events/{host['mine']}/attend/{gid}").status_code == 200
    assert client.get(f"/api/v1/events/{host['theirs']}/registrations").status_code == 403


def test_the_host_cancels_their_event(client, host):
    _login(client, "gert@test.ch")
    assert client.delete(f"/api/v1/events/{host['mine']}").status_code == 403
    _login(client, "hanna@test.ch")
    assert client.delete(f"/api/v1/events/{host['mine']}").status_code == 204
