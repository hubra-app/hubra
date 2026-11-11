"""Who is coming: names of an event's sign-ups for every member."""

from tests.events.test_m5_events import _create_event, _create_member


def test_participants_lists_coming_then_maybe(client, auth_headers, seeded_db):
    event_id = _create_event(client, auth_headers, title="BBQ").get_json()["id"]
    other = _create_member(
        client, auth_headers, email="anna@test.ch", first_name="Anna"
    ).get_json()["id"]
    client.post(f"/api/v1/events/{event_id}/maybe", headers=auth_headers)
    client.post(
        f"/api/v1/events/{event_id}/register/{other}", json={}, headers=auth_headers
    )

    resp = client.get(f"/api/v1/events/{event_id}/participants", headers=auth_headers)
    assert resp.status_code == 200
    rows = resp.get_json()
    assert [r["status"] for r in rows] == ["coming", "maybe"]
    assert rows[0]["member_id"] == other and rows[0]["name"].startswith("Anna")
    assert {"avatar_color", "guests"} <= rows[0].keys()


def test_participants_leave_out_cancelled_sign_ups(client, auth_headers, seeded_db):
    event_id = _create_event(client, auth_headers, title="Quiz").get_json()["id"]
    client.post(f"/api/v1/events/{event_id}/register", json={}, headers=auth_headers)
    client.post(f"/api/v1/events/{event_id}/cancel-registration", headers=auth_headers)

    rows = client.get(
        f"/api/v1/events/{event_id}/participants", headers=auth_headers
    ).get_json()
    assert rows == []


def test_participants_need_a_sign_in(client, auth_headers, seeded_db):
    event_id = _create_event(client, auth_headers, title="Closed").get_json()["id"]
    client.post("/api/v1/auth/logout")
    client.delete_cookie("access_token_cookie")
    resp = client.get(f"/api/v1/events/{event_id}/participants")
    assert resp.status_code == 401


def test_participants_of_a_missing_event_are_404(client, auth_headers, seeded_db):
    resp = client.get("/api/v1/events/999999/participants", headers=auth_headers)
    assert resp.status_code == 404
