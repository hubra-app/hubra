"""Editing a poll without closes_at keeps its deadline; null clears it."""


def test_editing_a_poll_keeps_its_deadline(client, auth_headers, seeded_db):
    poll_id = client.post(
        "/api/v1/polls/",
        json={
            "question": "Which day works best?",
            "options": [{"label": "Monday"}, {"label": "Friday"}],
            "closes_at": "2099-01-01T12:00:00+00:00",
        },
        headers=auth_headers,
    ).get_json()["id"]
    resp = client.patch(
        f"/api/v1/polls/{poll_id}",
        json={"question": "Which evening works best?"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["closes_at"].startswith("2099-01-01")
    resp = client.patch(
        f"/api/v1/polls/{poll_id}", json={"closes_at": None}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.get_json()["closes_at"] is None
