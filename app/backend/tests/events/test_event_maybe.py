"""'Vielleicht': a member may come; it takes no place."""

from tests.events.test_event_capacity_change import _statuses
from tests.events.test_m5_events import _create_event, _create_member


def test_maybe_takes_no_place_and_turns_into_a_sign_up(client, auth_headers, seeded_db):
    from hubra.api.events.services import EventService

    event_id = _create_event(
        client, auth_headers, title="BBQ", max_attendees=1
    ).get_json()["id"]
    resp = client.post(f"/api/v1/events/{event_id}/maybe", headers=auth_headers)
    assert resp.status_code == 200 and resp.get_json()["status"] == "maybe"
    assert EventService.places_taken(event_id) == 0
    assert EventService.maybe_count(event_id) == 1
    event = client.get(f"/api/v1/events/{event_id}", headers=auth_headers).get_json()
    assert event["my_status"] == "maybe"

    # Then a real sign-up: the same row, now with a place.
    resp = client.post(
        f"/api/v1/events/{event_id}/register", json={}, headers=auth_headers
    )
    assert resp.status_code == 201 and resp.get_json()["status"] == "registered"
    assert EventService.maybe_count(event_id) == 0
    assert EventService.places_taken(event_id) == 1


def test_maybe_gives_up_a_place_to_the_waitlist(client, auth_headers, seeded_db):
    event_id = _create_event(
        client, auth_headers, title="One Seat", max_attendees=1
    ).get_json()["id"]
    client.post(f"/api/v1/events/{event_id}/register", json={}, headers=auth_headers)
    other = _create_member(client, auth_headers, email="next@test.ch").get_json()["id"]
    client.post(
        f"/api/v1/events/{event_id}/register/{other}", json={}, headers=auth_headers
    )
    assert _statuses(event_id)[other] == "waitlisted"

    client.post(f"/api/v1/events/{event_id}/maybe", headers=auth_headers)
    statuses = _statuses(event_id)
    assert statuses[other] == "registered"
    assert "maybe" in statuses.values()


def test_maybe_can_be_withdrawn(client, auth_headers, seeded_db):
    event_id = _create_event(client, auth_headers, title="Quiz").get_json()["id"]
    client.post(f"/api/v1/events/{event_id}/maybe", headers=auth_headers)
    resp = client.post(
        f"/api/v1/events/{event_id}/cancel-registration", headers=auth_headers
    )
    assert resp.status_code == 200 and resp.get_json()["status"] == "cancelled"
