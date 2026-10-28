"""Tests for the polls blueprint (/api/v1/polls)."""


def _poll_payload(**overrides):
    payload = {
        "question": "Which day works best?",
        "options": [{"label": "Monday"}, {"label": "Friday"}],
    }
    payload.update(overrides)
    return payload


def _create_poll(client, auth_headers, **overrides):
    return client.post(
        "/api/v1/polls/", json=_poll_payload(**overrides), headers=auth_headers
    )


# ── Create ────────────────────────────────────────────────────────────────────


def test_create_poll(client, auth_headers, seeded_db):
    resp = _create_poll(client, auth_headers)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["question"] == "Which day works best?"
    assert len(body["options"]) == 2
    assert body["status"] == "open"


# ── Vote ──────────────────────────────────────────────────────────────────────


def test_vote_on_poll(client, auth_headers, seeded_db):
    poll_id = _create_poll(client, auth_headers).get_json()["id"]
    resp = client.post(
        f"/api/v1/polls/{poll_id}/vote",
        json={"option_index": 0},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["id"] == poll_id
    # The voted option should show vote_count >= 1
    assert body["options"][0]["vote_count"] >= 1


def test_revote_changes_choice(client, auth_headers, seeded_db):
    poll_id = _create_poll(client, auth_headers).get_json()["id"]
    client.post(
        f"/api/v1/polls/{poll_id}/vote", json={"option_index": 0}, headers=auth_headers
    )

    resp = client.post(
        f"/api/v1/polls/{poll_id}/vote",
        json={"option_index": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["options"][0]["vote_count"] == 0
    assert body["options"][1]["vote_count"] == 1


# ── Closed poll ───────────────────────────────────────────────────────────────


def test_vote_on_closed_poll(client, auth_headers, seeded_db):
    poll_id = _create_poll(client, auth_headers).get_json()["id"]

    # Close the poll first
    client.patch(f"/api/v1/polls/{poll_id}/close", headers=auth_headers)

    resp = client.post(
        f"/api/v1/polls/{poll_id}/vote",
        json={"option_index": 0},
        headers=auth_headers,
    )
    assert resp.status_code == 409


# ── Invalid option index ──────────────────────────────────────────────────────


def test_vote_invalid_option_index(client, auth_headers, seeded_db):
    poll_id = _create_poll(client, auth_headers).get_json()["id"]
    resp = client.post(
        f"/api/v1/polls/{poll_id}/vote",
        json={"option_index": 99},
        headers=auth_headers,
    )
    assert resp.status_code == 400


# ── Close poll ────────────────────────────────────────────────────────────────


def test_close_poll(client, auth_headers, seeded_db):
    poll_id = _create_poll(client, auth_headers).get_json()["id"]
    resp = client.patch(f"/api/v1/polls/{poll_id}/close", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "closed"


def test_poll_shows_my_vote(client, auth_headers, seeded_db):
    poll_id = _create_poll(client, auth_headers).get_json()["id"]
    listed = client.get("/api/v1/polls", headers=auth_headers).get_json()
    assert next(p for p in listed if p["id"] == poll_id)["my_vote"] is None

    client.post(
        f"/api/v1/polls/{poll_id}/vote", json={"option_index": 1}, headers=auth_headers
    )
    listed = client.get("/api/v1/polls", headers=auth_headers).get_json()
    assert next(p for p in listed if p["id"] == poll_id)["my_vote"] == 1
