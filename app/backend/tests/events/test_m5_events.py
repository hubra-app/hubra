"""Tests for M5 Events module — new fields, registration workflow, calendar export."""

from tests.helpers import add_member


def _create_event(client, auth_headers, **overrides):
    payload = {
        "title": "Open Shop Night",
        "date": "2030-06-06",
        "type": "Social",
    }
    payload.update(overrides)
    return client.post("/api/v1/events/", json=payload, headers=auth_headers)


def _create_member(client, auth_headers, **overrides):
    """Helper: a member with sensible defaults (they accepted an invite)."""
    payload = {
        "first_name": "Test",
        "last_name": "Member",
        "email": "member@test.ch",
    }
    payload.update(overrides)
    return add_member(client, auth_headers, **payload)


# ── New fields ───────────────────────────────────────────────────────────────


def test_create_event_with_new_fields(client, auth_headers, seeded_db):
    resp = _create_event(
        client,
        auth_headers,
        title="Workshop Day",
        date="2026-08-15",
        type="Workshop",
        description="Full day workshop",
        meeting_url="https://meet.example.com/abc",
        end_date="2026-08-16",
        all_day=True,
        category="training",
        max_attendees=20,
        requires_approval=True,
        is_public=True,
        cover_image_url="https://example.com/cover.jpg",
        color="#2596be",
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["description"] == "Full day workshop"
    assert body["meeting_url"] == "https://meet.example.com/abc"
    assert body["end_date"] == "2026-08-16"
    assert body["all_day"] is True
    assert body["category"] == "training"
    assert body["max_attendees"] == 20
    assert body["requires_approval"] is True
    assert body["is_public"] is True
    assert body["cover_image_url"] == "https://example.com/cover.jpg"
    assert body["color"] == "#2596be"


def test_update_event_new_fields(client, auth_headers, seeded_db):
    created = _create_event(client, auth_headers, title="Update Me")
    event_id = created.get_json()["id"]

    resp = client.patch(
        f"/api/v1/events/{event_id}",
        json={
            "description": "Updated description",
            "category": "meeting",
            "max_attendees": 50,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["description"] == "Updated description"
    assert body["category"] == "meeting"
    assert body["max_attendees"] == 50


def test_category_validation(client, auth_headers, seeded_db):
    resp = _create_event(
        client,
        auth_headers,
        category="invalid_category",
    )
    assert resp.status_code == 400


def test_list_filter_by_category(client, auth_headers, seeded_db):
    _create_event(client, auth_headers, title="Training Event", category="training")
    _create_event(client, auth_headers, title="Social Event", category="social")

    resp = client.get("/api/v1/events/?category=training", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    for e in body:
        assert e["category"] == "training"


# ── Registration workflow ─────────────────────────────────────────────────────


def test_register_for_event(client, auth_headers, seeded_db):
    event = _create_event(client, auth_headers, title="Register Me")
    event_id = event.get_json()["id"]

    resp = client.post(
        f"/api/v1/events/{event_id}/register",
        json={"notes": "Looking forward", "guests": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["status"] == "registered"
    assert body["notes"] == "Looking forward"
    assert body["guests"] == 1


def test_register_already_registered(client, auth_headers, seeded_db):
    event = _create_event(client, auth_headers, title="Already Reg")
    event_id = event.get_json()["id"]

    client.post(
        f"/api/v1/events/{event_id}/register",
        json={},
        headers=auth_headers,
    )

    resp = client.post(
        f"/api/v1/events/{event_id}/register",
        json={},
        headers=auth_headers,
    )
    assert resp.status_code == 409


def test_cancel_registration(client, auth_headers, seeded_db):
    event = _create_event(client, auth_headers, title="Cancel Reg")
    event_id = event.get_json()["id"]

    client.post(
        f"/api/v1/events/{event_id}/register",
        json={},
        headers=auth_headers,
    )

    resp = client.post(
        f"/api/v1/events/{event_id}/cancel-registration",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "cancelled"
    assert body["cancelled_at"] is not None


def test_cancel_no_registration(client, auth_headers, seeded_db):
    event = _create_event(client, auth_headers, title="No Reg")
    event_id = event.get_json()["id"]

    resp = client.post(
        f"/api/v1/events/{event_id}/cancel-registration",
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_mark_attendance(client, auth_headers, seeded_db):
    event = _create_event(client, auth_headers, title="Attend Me")
    event_id = event.get_json()["id"]

    member = _create_member(
        client,
        auth_headers,
        email="attend@test.ch",
        first_name="Attend",
        last_name="User",
    )
    member_id = member.get_json()["id"]

    client.post(
        f"/api/v1/events/{event_id}/register/{member_id}",
        json={},
        headers=auth_headers,
    )

    resp = client.post(
        f"/api/v1/events/{event_id}/attend/{member_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "attended"
    assert body["attended_at"] is not None


# ── Max attendees enforcement ─────────────────────────────────────────────────


def test_max_attendees_waitlist(client, auth_headers, seeded_db, db):
    event = _create_event(client, auth_headers, title="Full Event", max_attendees=1)
    event_id = event.get_json()["id"]

    member1 = _create_member(
        client,
        auth_headers,
        email="first@test.ch",
        first_name="First",
        last_name="Person",
    )
    member2 = _create_member(
        client,
        auth_headers,
        email="second@test.ch",
        first_name="Second",
        last_name="Person",
    )

    # First registration: registered
    resp = client.post(
        f"/api/v1/events/{event_id}/register/{member1.get_json()['id']}",
        json={},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.get_json()["status"] == "registered"

    # Second registration: waitlisted
    resp = client.post(
        f"/api/v1/events/{event_id}/register/{member2.get_json()['id']}",
        json={},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.get_json()["status"] == "waitlisted"


# ── Calendar export ───────────────────────────────────────────────────────────


def test_calendar_export(client, auth_headers, seeded_db):
    _create_event(client, auth_headers, title="Calendar Event", date="2026-09-01")

    resp = client.get("/api/v1/events/calendar", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.mimetype == "text/calendar"
    data = resp.data.decode()
    assert "BEGIN:VCALENDAR" in data
    assert "END:VCALENDAR" in data
    assert "Calendar Event" in data
    assert "DTSTART;VALUE=DATE:20260901" in data


def test_calendar_export_empty(client, auth_headers, seeded_db):
    resp = client.get("/api/v1/events/calendar", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.data.decode()
    assert "BEGIN:VCALENDAR" in data
    assert "END:VCALENDAR" in data


def test_register_again_after_cancelling(client, auth_headers, seeded_db):
    """A member who cancelled can sign up again (one registration row per
    member and event, so the cancelled one comes back)."""
    event_id = _create_event(client, auth_headers, title="Back Again").get_json()["id"]
    client.post(f"/api/v1/events/{event_id}/register", json={}, headers=auth_headers)
    client.post(f"/api/v1/events/{event_id}/cancel-registration", headers=auth_headers)

    resp = client.post(
        f"/api/v1/events/{event_id}/register",
        json={"guests": 2},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["status"] == "registered"
    assert body["guests"] == 2
    assert body["cancelled_at"] is None


def test_cancelling_frees_the_place_for_the_waitlist(client, auth_headers, seeded_db):
    """When a registered member cancels, the first one on the waitlist gets
    the place."""
    event_id = _create_event(
        client, auth_headers, title="One Seat", max_attendees=1
    ).get_json()["id"]
    first = _create_member(client, auth_headers, email="first@test.ch").get_json()["id"]
    second = _create_member(client, auth_headers, email="second@test.ch").get_json()["id"]

    client.post(f"/api/v1/events/{event_id}/register", json={}, headers=auth_headers)
    for member_id in (first, second):
        resp = client.post(
            f"/api/v1/events/{event_id}/register/{member_id}",
            json={},
            headers=auth_headers,
        )
        assert resp.get_json()["status"] == "waitlisted"

    client.post(f"/api/v1/events/{event_id}/cancel-registration", headers=auth_headers)

    from sqlalchemy import select

    from hubra.core.extensions import db
    from hubra.core.models.event import EventRegistration

    regs = dict(
        db.session.execute(
            select(EventRegistration.member_id, EventRegistration.status).where(
                EventRegistration.event_id == event_id
            )
        ).all()
    )
    assert regs[first] == "registered"
    assert regs[second] == "waitlisted"
    # Only members with a place show as attending.
    attendees = client.get(f"/api/v1/events/{event_id}", headers=auth_headers)
    assert attendees.get_json()["attendee_ids"] == [first]


# ── Deadlines (stored before, but never checked) ────────────────────────────


def test_no_sign_up_after_the_registration_deadline(client, auth_headers, seeded_db):
    event_id = _create_event(
        client, auth_headers, registration_deadline="2020-01-01T12:00:00+00:00"
    ).get_json()["id"]

    resp = client.post(f"/api/v1/events/{event_id}/register", json={}, headers=auth_headers)
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "REGISTRATION_CLOSED"

    # An organiser can still add someone.
    resp = client.post(
        f"/api/v1/events/{event_id}/register/{seeded_db['admin'].id}",
        json={},
        headers=auth_headers,
    )
    assert resp.status_code == 201


def test_no_sign_up_for_a_past_event(client, auth_headers, seeded_db):
    event_id = _create_event(client, auth_headers, date="2020-05-05").get_json()["id"]
    resp = client.post(f"/api/v1/events/{event_id}/register", json={}, headers=auth_headers)
    assert resp.status_code == 409


def test_open_deadline_still_takes_sign_ups(client, auth_headers, seeded_db):
    event_id = _create_event(
        client, auth_headers, registration_deadline="2030-01-01T12:00:00+00:00"
    ).get_json()["id"]
    resp = client.post(f"/api/v1/events/{event_id}/register", json={}, headers=auth_headers)
    assert resp.status_code == 201


def test_no_cancelling_after_the_cancellation_deadline(client, auth_headers, db, seeded_db):
    from datetime import datetime, timezone

    from hubra.core.models.event import ClubEvent

    event_id = _create_event(client, auth_headers).get_json()["id"]
    url = f"/api/v1/events/{event_id}"
    assert client.post(f"{url}/register", json={}, headers=auth_headers).status_code == 201

    db.session.get(ClubEvent, event_id).cancellation_deadline = datetime(
        2020, 1, 1, tzinfo=timezone.utc
    )
    db.session.commit()

    resp = client.post(f"{url}/cancel-registration", headers=auth_headers)
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "CANCELLATION_CLOSED"
