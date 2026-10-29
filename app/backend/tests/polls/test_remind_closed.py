"""A closed poll sends no "please vote" reminders."""

from tests.polls.test_polls import _create_poll


def test_no_reminder_for_a_closed_poll(client, auth_headers, seeded_db):
    poll_id = _create_poll(client, auth_headers).get_json()["id"]
    client.patch(f"/api/v1/polls/{poll_id}/close", json={}, headers=auth_headers)

    resp = client.post(f"/api/v1/polls/{poll_id}/remind", headers=auth_headers)
    assert resp.status_code == 409
