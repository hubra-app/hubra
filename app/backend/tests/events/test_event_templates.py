"""Event templates: save an event, start new ones from it (roadmap idea 15)."""

from tests.events.test_m5_events import _create_event, _create_member

URL = "/api/v1/events/templates"


def test_save_list_and_delete_a_template(client, auth_headers, seeded_db):
    event = _create_event(
        client,
        auth_headers,
        title="Training",
        date="2030-06-06",
        end_date="2030-06-07",
        time="18:30",
        location="Halle",
        max_attendees=20,
        requires_approval=True,
        description="Mit Turnschuhen",
    ).get_json()

    resp = client.post(
        URL,
        json={"event_id": event["id"], "name": "Dienstagstraining"},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.get_json()
    saved = resp.get_json()
    assert saved["name"] == "Dienstagstraining"
    data = saved["data"]
    assert data["title"] == "Training"
    assert data["time"] == "18:30"
    assert data["location"] == "Halle"
    assert data["max_attendees"] == 20
    assert data["requires_approval"] is True
    assert data["days"] == 1
    assert "date" not in data

    listed = client.get(URL, headers=auth_headers).get_json()
    assert [t["name"] for t in listed] == ["Dienstagstraining"]

    assert (
        client.delete(f"{URL}/{saved['id']}", headers=auth_headers).status_code == 204
    )
    assert client.get(URL, headers=auth_headers).get_json() == []
    assert (
        client.delete(f"{URL}/{saved['id']}", headers=auth_headers).status_code == 404
    )


def test_the_name_defaults_to_the_title(client, auth_headers, seeded_db):
    event = _create_event(client, auth_headers, title="Grillabend").get_json()
    resp = client.post(URL, json={"event_id": event["id"]}, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.get_json()["name"] == "Grillabend"


def test_bad_input(client, auth_headers, seeded_db):
    assert client.post(URL, json={}, headers=auth_headers).status_code == 400
    assert (
        client.post(URL, json={"event_id": 999}, headers=auth_headers).status_code
        == 404
    )


def test_templates_need_sign_in(client, seeded_db):
    assert client.get(URL).status_code == 401
    assert client.post(URL, json={"event_id": 1}).status_code == 401


def test_templates_need_the_create_right(client, auth_headers, seeded_db):
    event = _create_event(client, auth_headers).get_json()
    _create_member(client, auth_headers, email="anna@test.ch")
    client.post(
        "/api/v1/auth/login",
        json={"email": "anna@test.ch", "password": "Member-Pass-123!"},
    )
    assert client.get(URL).status_code == 403
    assert client.post(URL, json={"event_id": event["id"]}).status_code == 403
