"""Self-join (interest) groups and the group.membership_changed event."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from hubra.core.models.group import Group


@pytest.fixture
def groups(db, seeded_db):
    open_group = Group(name="Climbing", type="interest_group", self_join=True)
    closed = Group(name="Board", type="board")
    db.session.add_all([open_group, closed])
    db.session.commit()
    return open_group, closed


def test_joinable_lists_only_self_join_groups(client, auth_headers, groups):
    listed = client.get("/api/v1/groups/joinable").get_json()
    assert [(g["name"], g["joined"]) for g in listed] == [("Climbing", False)]


def test_join_and_leave(client, auth_headers, groups):
    open_group, _ = groups
    with patch("hubra.api.groups.services.emit") as emit:
        assert client.post(f"/api/v1/groups/{open_group.id}/join").status_code == 204
        emit.assert_called_once()
        assert emit.call_args.kwargs["action"] == "joined"
    listed = client.get("/api/v1/groups/joinable").get_json()
    assert listed[0]["joined"] is True and listed[0]["memberCount"] == 1
    assert client.post(f"/api/v1/groups/{open_group.id}/join").status_code == 409
    assert client.post(f"/api/v1/groups/{open_group.id}/leave").status_code == 204
    assert client.post(f"/api/v1/groups/{open_group.id}/leave").status_code == 404


def test_cannot_join_closed_group(client, auth_headers, groups):
    _, closed = groups
    resp = client.post(f"/api/v1/groups/{closed.id}/join")
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "GROUP_NOT_SELF_JOIN"
    assert client.post("/api/v1/groups/9999/join").status_code == 404


def test_self_join_flag_is_editable(client, auth_headers, groups):
    _, closed = groups
    resp = client.patch(f"/api/v1/groups/{closed.id}", json={"self_join": True})
    assert resp.status_code == 200
    assert resp.get_json()["self_join"] is True
