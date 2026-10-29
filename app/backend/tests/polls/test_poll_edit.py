"""Editing a poll, reminders and deleting it.

The club app sends the options with every edit, and replacing them deleted
every vote already cast, so moving the closing date wiped the result.
"""

OPTIONS = [{"label": "Monday"}, {"label": "Friday"}]


def _poll(client, headers, **fields):
    body = {"question": "Which day works best?", "options": OPTIONS, **fields}
    resp = client.post("/api/v1/polls/", json=body, headers=headers)
    assert resp.status_code == 201
    return resp.get_json()["id"]


def _vote(client, headers, poll_id, index=1):
    resp = client.post(
        f"/api/v1/polls/{poll_id}/vote", json={"option_index": index}, headers=headers
    )
    assert resp.status_code == 200


def test_edit_with_the_same_options_keeps_the_votes(client, auth_headers, seeded_db):
    poll_id = _poll(client, auth_headers)
    _vote(client, auth_headers, poll_id)

    resp = client.patch(
        f"/api/v1/polls/{poll_id}",
        json={
            "question": "Which day works best for you?",
            "options": OPTIONS,
            "closes_at": "2030-01-01T18:00:00+00:00",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["question"] == "Which day works best for you?"
    assert body["total_votes"] == 1
    assert [o["vote_count"] for o in body["options"]] == [0, 1]


def test_options_cannot_change_once_votes_are_in(client, auth_headers, seeded_db):
    poll_id = _poll(client, auth_headers)
    _vote(client, auth_headers, poll_id)

    resp = client.patch(
        f"/api/v1/polls/{poll_id}",
        json={"options": [{"label": "Monday"}, {"label": "Saturday"}]},
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "POLL_HAS_VOTES"
    poll = client.get(f"/api/v1/polls/{poll_id}", headers=auth_headers).get_json()
    assert poll["total_votes"] == 1


def test_options_change_freely_before_any_vote(client, auth_headers, seeded_db):
    poll_id = _poll(client, auth_headers)
    resp = client.patch(
        f"/api/v1/polls/{poll_id}",
        json={"options": [{"label": "Tuesday"}, {"label": "Thursday"}, {"label": "Sunday"}]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert [o["label"] for o in resp.get_json()["options"]] == [
        "Tuesday",
        "Thursday",
        "Sunday",
    ]


def test_remind_reaches_required_members_who_have_not_voted(
    client, auth_headers, seeded_db, db
):
    from hubra.core.models.group import Group
    from hubra.core.models.member import Member
    from hubra.core.models.notification import Notification
    from hubra.core.models.user import User

    admin = db.session.get(Member, seeded_db["admin"].id)
    other_user = User(email="board@test.ch", first_name="Bea", last_name="Board")
    other_user.set_password("password123")
    db.session.add(other_user)
    db.session.flush()
    other = Member(user_id=other_user.id, status="active")
    group = Group(name="Vorstand")
    group.members = [admin, other]
    db.session.add_all([other, group])
    db.session.commit()

    poll_id = _poll(
        client, auth_headers, is_required=True, required_group_ids=[group.id]
    )
    _vote(client, auth_headers, poll_id)

    resp = client.post(f"/api/v1/polls/{poll_id}/remind", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json() == {"sent": 1}
    reminded = db.session.query(Notification.member_id).filter(
        Notification.title.like("Reminder:%")
    )
    assert [row[0] for row in reminded] == [other.id]


def test_delete_a_poll_with_votes(client, auth_headers, seeded_db):
    poll_id = _poll(client, auth_headers)
    _vote(client, auth_headers, poll_id)
    assert client.delete(f"/api/v1/polls/{poll_id}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/v1/polls/{poll_id}", headers=auth_headers).status_code == 404


def test_a_poll_past_its_closing_time_shows_as_closed(client, auth_headers, seeded_db):
    poll_id = _poll(client, auth_headers, closes_at="2020-01-01T12:00:00+00:00")
    poll = client.get(f"/api/v1/polls/{poll_id}", headers=auth_headers).get_json()
    assert poll["status"] == "closed"
    listed = client.get("/api/v1/polls/", headers=auth_headers).get_json()
    rows = listed["data"] if isinstance(listed, dict) else listed
    assert next(p for p in rows if p["id"] == poll_id)["status"] == "closed"
