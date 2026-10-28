"""Tests for the events blueprint (/api/v1/events)."""


def _event_payload(**overrides):
    payload = {
        "title": "Open Shop Night",
        "date": "2026-06-06",
        "type": "Social",
    }
    payload.update(overrides)
    return payload


def _create_event(client, auth_headers, **overrides):
    return client.post(
        "/api/v1/events/", json=_event_payload(**overrides), headers=auth_headers
    )


# ── Create ────────────────────────────────────────────────────────────────────


def test_create_event(client, auth_headers, seeded_db):
    resp = _create_event(client, auth_headers)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["title"] == "Open Shop Night"
    assert body["type"] == "Social"
    assert body["attendee_ids"] == []


# ── List ──────────────────────────────────────────────────────────────────────


def test_list_events(client, auth_headers, seeded_db):
    _create_event(client, auth_headers, title="Event A", date="2026-07-01")
    _create_event(client, auth_headers, title="Event B", date="2026-06-01")
    resp = client.get("/api/v1/events/", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body) == 2
    # Ordered by date ascending
    assert body[0]["title"] == "Event B"


# ── Get ───────────────────────────────────────────────────────────────────────


def test_get_event(client, auth_headers, seeded_db):
    event_id = _create_event(client, auth_headers).get_json()["id"]
    resp = client.get(f"/api/v1/events/{event_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["id"] == event_id


def test_get_event_not_found(client, auth_headers, seeded_db):
    resp = client.get("/api/v1/events/9999", headers=auth_headers)
    assert resp.status_code == 404


# ── Update ────────────────────────────────────────────────────────────────────


def test_update_event(client, auth_headers, seeded_db):
    event_id = _create_event(client, auth_headers).get_json()["id"]
    resp = client.patch(
        f"/api/v1/events/{event_id}",
        json={"title": "Updated title", "location": "Workshop"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["title"] == "Updated title"
    assert body["location"] == "Workshop"


# ── Delete ────────────────────────────────────────────────────────────────────


def test_delete_event(client, auth_headers, seeded_db):
    event_id = _create_event(client, auth_headers).get_json()["id"]
    resp = client.delete(f"/api/v1/events/{event_id}", headers=auth_headers)
    assert resp.status_code == 204
    resp = client.get(f"/api/v1/events/{event_id}", headers=auth_headers)
    assert resp.status_code == 404


# ── Attendees ─────────────────────────────────────────────────────────────────


def test_add_attendee(client, auth_headers, seeded_db):
    event_id = _create_event(client, auth_headers).get_json()["id"]
    member_id = seeded_db["admin"].id
    resp = client.post(
        f"/api/v1/events/{event_id}/attendees/{member_id}", headers=auth_headers
    )
    assert resp.status_code == 204
    body = client.get(f"/api/v1/events/{event_id}", headers=auth_headers).get_json()
    assert member_id in body["attendee_ids"]


def test_add_attendee_conflict(client, auth_headers, seeded_db):
    event_id = _create_event(client, auth_headers).get_json()["id"]
    member_id = seeded_db["admin"].id
    client.post(
        f"/api/v1/events/{event_id}/attendees/{member_id}", headers=auth_headers
    )
    resp = client.post(
        f"/api/v1/events/{event_id}/attendees/{member_id}", headers=auth_headers
    )
    assert resp.status_code == 409


def test_remove_attendee(client, auth_headers, seeded_db):
    event_id = _create_event(client, auth_headers).get_json()["id"]
    member_id = seeded_db["admin"].id
    client.post(
        f"/api/v1/events/{event_id}/attendees/{member_id}", headers=auth_headers
    )
    resp = client.delete(
        f"/api/v1/events/{event_id}/attendees/{member_id}", headers=auth_headers
    )
    assert resp.status_code == 204


def test_remove_not_attending(client, auth_headers, seeded_db):
    event_id = _create_event(client, auth_headers).get_json()["id"]
    member_id = seeded_db["admin"].id
    resp = client.delete(
        f"/api/v1/events/{event_id}/attendees/{member_id}", headers=auth_headers
    )
    assert resp.status_code == 404


# ── Filtering ─────────────────────────────────────────────────────────────────


def test_filter_by_type(client, auth_headers, seeded_db):
    _create_event(client, auth_headers, title="W1", type="Workshop")
    _create_event(client, auth_headers, title="S1", type="Social")
    resp = client.get("/api/v1/events/?type=Workshop", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body) == 1
    assert body[0]["title"] == "W1"


def test_invalid_date_range(client, auth_headers, seeded_db):
    resp = client.get("/api/v1/events/?from=not-a-date", headers=auth_headers)
    assert resp.status_code == 400


# ── Validation ────────────────────────────────────────────────────────────────


def test_create_event_validation(client, auth_headers, seeded_db):
    resp = client.post(
        "/api/v1/events/",
        json={"date": "2026-06-06", "type": "Social"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
