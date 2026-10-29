"""Raising an event's limit gives the waitlist the new places."""

from sqlalchemy import select

from tests.events.test_m5_events import _create_event, _create_member


def _statuses(event_id):
    from hubra.core.extensions import db
    from hubra.core.models.event import EventRegistration

    return dict(
        db.session.execute(
            select(EventRegistration.member_id, EventRegistration.status).where(
                EventRegistration.event_id == event_id
            )
        ).all()
    )


def test_more_places_move_the_waitlist_up(client, auth_headers, seeded_db):
    event_id = _create_event(
        client, auth_headers, title="Two Seats", max_attendees=1
    ).get_json()["id"]
    ids = [
        _create_member(client, auth_headers, email=f"m{i}@test.ch").get_json()["id"]
        for i in range(3)
    ]
    for member_id in ids:
        client.post(
            f"/api/v1/events/{event_id}/register/{member_id}", json={}, headers=auth_headers
        )
    assert list(_statuses(event_id).values()).count("waitlisted") == 2

    resp = client.patch(
        f"/api/v1/events/{event_id}", json={"max_attendees": 2}, headers=auth_headers
    )
    assert resp.status_code == 200
    statuses = _statuses(event_id)
    assert [statuses[i] for i in ids] == ["registered", "registered", "waitlisted"]

    client.patch(
        f"/api/v1/events/{event_id}", json={"max_attendees": None}, headers=auth_headers
    )
    assert set(_statuses(event_id).values()) == {"registered"}
    event = client.get(f"/api/v1/events/{event_id}", headers=auth_headers).get_json()
    assert sorted(event["attendee_ids"]) == sorted(ids)


def test_a_member_who_gets_a_place_is_told(client, auth_headers, seeded_db):
    from hubra.core.extensions import db
    from hubra.core.models.notification import Notification

    event_id = _create_event(
        client, auth_headers, title="Last Seat", max_attendees=1
    ).get_json()["id"]
    first, second = (
        _create_member(client, auth_headers, email=f"w{i}@test.ch").get_json()["id"]
        for i in range(2)
    )
    for member_id in (first, second):
        client.post(
            f"/api/v1/events/{event_id}/register/{member_id}", json={}, headers=auth_headers
        )
    resp = client.delete(
        f"/api/v1/events/{event_id}/attendees/{first}", headers=auth_headers
    )
    assert resp.status_code == 204
    assert _statuses(event_id) == {first: "cancelled", second: "registered"}

    titles = db.session.scalars(
        select(Notification.msg).where(
            Notification.member_id == second, Notification.title == "You got a place"
        )
    ).all()
    assert titles == ["Last Seat"]


def test_members_hear_when_their_event_is_deleted(client, auth_headers, seeded_db):
    from hubra.core.extensions import db
    from hubra.core.models.notification import Notification

    event_id = _create_event(client, auth_headers, title="Ausflug").get_json()["id"]
    member_id = _create_member(client, auth_headers, email="x@test.ch").get_json()["id"]
    client.post(
        f"/api/v1/events/{event_id}/register/{member_id}", json={}, headers=auth_headers
    )
    assert client.delete(f"/api/v1/events/{event_id}", headers=auth_headers).status_code == 204

    titles = db.session.scalars(
        select(Notification.msg).where(
            Notification.member_id == member_id, Notification.title == "Event cancelled"
        )
    ).all()
    assert titles == ["Ausflug"]


def test_an_event_cannot_end_before_it_starts(client, auth_headers, seeded_db):
    resp = _create_event(client, auth_headers, date="2030-06-06", end_date="2030-06-05")
    assert resp.status_code == 400
    event_id = _create_event(client, auth_headers, date="2030-06-06").get_json()["id"]
    resp = client.patch(
        f"/api/v1/events/{event_id}", json={"end_date": "2030-06-01"}, headers=auth_headers
    )
    assert resp.status_code == 400
    resp = client.patch(
        f"/api/v1/events/{event_id}", json={"end_date": "2030-06-08"}, headers=auth_headers
    )
    assert resp.status_code == 200


def test_members_hear_when_their_event_moves(client, auth_headers, seeded_db):
    from hubra.core.extensions import db
    from hubra.core.models.notification import Notification

    event_id = _create_event(client, auth_headers, title="Grillabend").get_json()["id"]
    member_id = _create_member(client, auth_headers, email="g@test.ch").get_json()["id"]
    client.post(
        f"/api/v1/events/{event_id}/register/{member_id}", json={}, headers=auth_headers
    )
    url = f"/api/v1/events/{event_id}"
    client.patch(url, json={"description": "Bring a salad"}, headers=auth_headers)
    client.patch(url, json={"date": "2030-06-07"}, headers=auth_headers)

    told = db.session.scalars(
        select(Notification.msg).where(
            Notification.member_id == member_id, Notification.title == "Event changed"
        )
    ).all()
    assert told == ["Grillabend"]
