"""The leader of a group runs it without the club-wide group rights: who is
in it and how it presents itself. Its name, leader and mail alias stay with
the club, and other groups stay closed."""

import pytest

from tests.settings.test_settings_kv import _login, _make_role_and_member


@pytest.fixture
def team(client, app, db, seeded_db):
    from hubra.core.models.group import Group

    app.test_cli_runner().invoke(args=["sync-permissions"])
    tier = seeded_db["tier"]
    lead = _make_role_and_member(db, tier, name="Lea", permission_keys=[])
    newbie = _make_role_and_member(db, tier, name="Nico", permission_keys=[])
    mine = Group(name="Youth", lead_id=lead.id)
    other = Group(name="Seniors")
    db.session.add_all([mine, other])
    db.session.commit()
    return {"mine": mine.id, "other": other.id, "newbie": newbie.id}


def test_the_leader_adds_and_removes_members(client, team):
    _login(client, "lea@test.ch")
    url = f"/api/v1/groups/{team['mine']}/members/{team['newbie']}"
    assert client.post(url).status_code == 204
    members = client.get(f"/api/v1/groups/{team['mine']}/members").get_json()["data"]
    assert [m["id"] for m in members] == [team["newbie"]]
    assert client.delete(url).status_code == 204
    other = f"/api/v1/groups/{team['other']}/members/{team['newbie']}"
    assert client.post(other).status_code == 403


def test_the_leader_edits_how_the_group_presents_itself(client, team):
    _login(client, "lea@test.ch")
    url = f"/api/v1/groups/{team['mine']}"
    r = client.patch(url, json={"description": "Under 18", "name": "Mine", "lead_id": None})
    assert r.status_code == 200
    body = r.get_json()
    assert body["description"] == "Under 18"
    assert body["name"] == "Youth" and body["lead_id"] is not None
    assert client.patch(f"/api/v1/groups/{team['other']}", json={"description": "x"}).status_code == 403
    assert client.delete(url).status_code == 403


def test_a_member_is_not_a_leader(client, team):
    _login(client, "nico@test.ch")
    url = f"/api/v1/groups/{team['mine']}/members/{team['newbie']}"
    assert client.post(url).status_code == 403
    assert client.patch(f"/api/v1/groups/{team['mine']}", json={"description": "x"}).status_code == 403
