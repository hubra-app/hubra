"""Events that need approval hold sign-ups until an organiser decides, and
guests take places against the limit."""

from tests.events.test_event_capacity_change import _statuses
from tests.events.test_m5_events import _create_event, _create_member
from tests.settings.test_settings_kv import _login, _make_role_and_member

_MEMBER = ["events.events.read", "events.events.register"]


def _member_signs_up(client, app, db, seeded_db, event_id, **body):
    app.test_cli_runner().invoke(args=["sync-permissions"])
    _make_role_and_member(db, seeded_db["tier"], name="Joiner", permission_keys=_MEMBER)
    _login(client, "joiner@test.ch")
    resp = client.post(f"/api/v1/events/{event_id}/register", json=body)
    mine = client.get(f"/api/v1/events/{event_id}").get_json()
    _login(client, "admin@test.ch")
    return resp, mine


def test_a_sign_up_waits_for_approval(client, app, db, seeded_db, auth_headers):
    event_id = _create_event(
        client, auth_headers, title="Vetted", requires_approval=True
    ).get_json()["id"]

    resp, mine = _member_signs_up(client, app, db, seeded_db, event_id)
    assert resp.status_code == 201
    assert resp.get_json()["status"] == "pending"
    assert mine["my_status"] == "pending"
    assert mine["attendee_ids"] == []

    event = client.get(f"/api/v1/events/{event_id}").get_json()
    assert event["pending_count"] == 1 and event["places_taken"] == 0
    pending = client.get(f"/api/v1/events/{event_id}/registrations?status=pending")
    [reg] = pending.get_json()
    member_id = reg["member_id"]

    ok = client.post(f"/api/v1/events/{event_id}/registrations/{member_id}/approve")
    assert ok.status_code == 200 and ok.get_json()["status"] == "approved"
    event = client.get(f"/api/v1/events/{event_id}").get_json()
    assert event["attendee_ids"] == [member_id] and event["places_taken"] == 1

    again = client.post(f"/api/v1/events/{event_id}/registrations/{member_id}/decline")
    assert again.status_code == 409


def test_a_declined_sign_up_takes_no_place(client, app, db, seeded_db, auth_headers):
    event_id = _create_event(
        client, auth_headers, title="Vetted", requires_approval=True, max_attendees=1
    ).get_json()["id"]
    _member_signs_up(client, app, db, seeded_db, event_id)
    [member_id] = _statuses(event_id)

    resp = client.post(f"/api/v1/events/{event_id}/registrations/{member_id}/decline")
    assert resp.get_json()["status"] == "declined"
    assert client.get(f"/api/v1/events/{event_id}").get_json()["places_taken"] == 0


def test_switching_approval_off_lets_the_waiting_in(
    client, app, db, seeded_db, auth_headers
):
    event_id = _create_event(
        client, auth_headers, title="Vetted", requires_approval=True
    ).get_json()["id"]
    _member_signs_up(client, app, db, seeded_db, event_id)

    client.patch(f"/api/v1/events/{event_id}", json={"requires_approval": False})
    assert set(_statuses(event_id).values()) == {"approved"}


def test_an_organiser_signing_someone_up_approves_it(client, auth_headers, seeded_db):
    event_id = _create_event(
        client, auth_headers, title="Vetted", requires_approval=True
    ).get_json()["id"]
    member_id = _create_member(client, auth_headers, email="o@test.ch").get_json()["id"]
    resp = client.post(
        f"/api/v1/events/{event_id}/register/{member_id}", json={}, headers=auth_headers
    )
    assert resp.get_json()["status"] == "approved"


def test_guests_take_places(client, auth_headers, seeded_db):
    event_id = _create_event(
        client, auth_headers, title="Three Seats", max_attendees=3
    ).get_json()["id"]
    a, b, c = (
        _create_member(client, auth_headers, email=f"g{i}@test.ch").get_json()["id"]
        for i in range(3)
    )

    def sign_up(member_id, guests):
        return client.post(
            f"/api/v1/events/{event_id}/register/{member_id}",
            json={"guests": guests},
            headers=auth_headers,
        ).get_json()["status"]

    assert sign_up(a, 1) == "registered"  # 2 of 3 places
    assert sign_up(b, 1) == "waitlisted"  # needs 2, 1 left
    assert sign_up(c, 0) == "waitlisted"  # behind b in line
    assert client.get(f"/api/v1/events/{event_id}").get_json()["places_taken"] == 2

    # a leaves: b and their guest move up, then c fits the last place.
    client.delete(f"/api/v1/events/{event_id}/attendees/{a}", headers=auth_headers)
    statuses = _statuses(event_id)
    assert (statuses[b], statuses[c]) == ("registered", "registered")
    assert client.get(f"/api/v1/events/{event_id}").get_json()["places_taken"] == 3
