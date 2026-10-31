"""Whoever asked the question runs the poll, and a poll for named groups
or functions is theirs to vote on."""

import pytest

from tests.settings.test_settings_kv import _login, _make_role_and_member

_VOTER = ["polls.polls.read", "polls.polls.vote"]


@pytest.fixture
def people(client, app, db, seeded_db):
    from hubra.core.models.group import Group

    app.test_cli_runner().invoke(args=["sync-permissions"])
    tier = seeded_db["tier"]
    asker = _make_role_and_member(
        db, tier, name="Anna", permission_keys=_VOTER + ["polls.polls.create"]
    )
    inside = _make_role_and_member(db, tier, name="Ines", permission_keys=_VOTER)
    _make_role_and_member(db, tier, name="Olaf", permission_keys=_VOTER)
    board = Group(name="Board")
    board.members.append(inside)
    db.session.add(board)
    db.session.commit()
    return {"asker": asker, "board": board.id}


def _ask(client, **extra):
    body = {"question": "Picnic?", "options": [{"label": "Yes"}, {"label": "No"}]}
    return client.post("/api/v1/polls/", json=body | extra).get_json()["id"]


def test_the_asker_runs_their_own_poll(client, people):
    _login(client, "admin@test.ch")
    theirs = _ask(client)
    _login(client, "anna@test.ch")
    mine = _ask(client)
    assert client.patch(f"/api/v1/polls/{mine}", json={"question": "BBQ?"}).status_code == 200
    assert client.patch(f"/api/v1/polls/{theirs}", json={"question": "x"}).status_code == 403
    assert client.patch(f"/api/v1/polls/{theirs}/close").status_code == 403
    assert client.patch(f"/api/v1/polls/{mine}/close").status_code == 200
    _login(client, "olaf@test.ch")
    assert client.patch(f"/api/v1/polls/{mine}", json={"question": "x"}).status_code == 403


def test_a_board_poll_is_for_the_board(client, people):
    _login(client, "anna@test.ch")
    poll = _ask(client, required_group_ids=[people["board"]], allow_proxy=True)
    _login(client, "olaf@test.ch")
    assert client.get(f"/api/v1/polls/{poll}").get_json()["may_vote"] is False
    r = client.post(f"/api/v1/polls/{poll}/vote", json={"option_index": 0})
    assert r.status_code == 403 and r.get_json()["error"] == "NOT_ELIGIBLE"
    _login(client, "ines@test.ch")
    assert client.get(f"/api/v1/polls/{poll}").get_json()["may_vote"] is True
    assert client.post(f"/api/v1/polls/{poll}/vote", json={"option_index": 0}).status_code == 200


def test_an_open_poll_takes_every_vote(client, people):
    _login(client, "anna@test.ch")
    poll = _ask(client)
    _login(client, "olaf@test.ch")
    assert client.get("/api/v1/polls/").get_json()[0]["may_vote"] is True
    assert client.post(f"/api/v1/polls/{poll}/vote", json={"option_index": 1}).status_code == 200
