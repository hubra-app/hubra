"""Tests for M5 Groups module — new fields, member roles, mailing list, nested groups."""

from tests.helpers import add_member


def _create_group(client, auth_headers, **overrides):
    payload = {
        "name": "Test Group",
        "description": "A test group",
        "color": "#6366f1",
    }
    payload.update(overrides)
    return client.post("/api/v1/groups/", json=payload, headers=auth_headers)


def _create_member(client, auth_headers, **overrides):
    """Helper: a member with sensible defaults (they accepted an invite)."""
    payload = {
        "first_name": "Test",
        "last_name": "Member",
        "email": "member@test.ch",
    }
    payload.update(overrides)
    return add_member(client, auth_headers, **payload)


# ── New fields ───────────────────────────────────────────────────────────────


def test_create_group_with_new_fields(client, auth_headers, seeded_db):
    resp = _create_group(
        client,
        auth_headers,
        name="Board",
        type="board",
        email_alias="board@club.ch",
        visibility="private",
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["type"] == "board"
    assert body["email_alias"] == "board@club.ch"
    assert body["visibility"] == "private"


def test_create_group_type_validation(client, auth_headers, seeded_db):
    resp = _create_group(
        client,
        auth_headers,
        name="Bad Type",
        type="invalid_type",
    )
    assert resp.status_code == 400


def test_group_type_defaults_to_interest_group(client, auth_headers, seeded_db):
    resp = _create_group(client, auth_headers, name="Defaults")
    assert resp.status_code == 201
    assert resp.get_json()["type"] == "interest_group"


def test_update_group_new_fields(client, auth_headers, seeded_db):
    created = _create_group(client, auth_headers, name="Update Me")
    group_id = created.get_json()["id"]

    resp = client.patch(
        f"/api/v1/groups/{group_id}",
        json={
            "type": "committee",
            "email_alias": "committee@club.ch",
            "visibility": "private",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["type"] == "committee"
    assert body["email_alias"] == "committee@club.ch"
    assert body["visibility"] == "private"


# ── Nested groups ────────────────────────────────────────────────────────────


def test_nested_group_parent(client, auth_headers, seeded_db):
    parent = _create_group(client, auth_headers, name="Parent Group")
    parent_id = parent.get_json()["id"]

    child = _create_group(
        client,
        auth_headers,
        name="Child Group",
        parent_group_id=parent_id,
    )
    assert child.status_code == 201
    body = child.get_json()
    assert body["parent_group_id"] == parent_id
    assert body["parent_group_name"] == "Parent Group"


# ── Member roles ─────────────────────────────────────────────────────────────


def test_update_member_role(client, auth_headers, seeded_db):
    group = _create_group(client, auth_headers, name="Role Group")
    group_id = group.get_json()["id"]

    member = _create_member(
        client,
        auth_headers,
        email="rolemember@test.ch",
        first_name="Role",
        last_name="Member",
    )
    member_id = member.get_json()["id"]

    # Add member to group
    resp = client.post(
        f"/api/v1/groups/{group_id}/members/{member_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 204

    # Update role to leader
    resp = client.patch(
        f"/api/v1/groups/{group_id}/members/{member_id}",
        json={"role": "leader", "notes": "Group leader"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["role"] == "leader"
    assert body["notes"] == "Group leader"
    assert body["member_id"] == member_id
    assert body["member_name"] == "Role Member"


def test_update_member_role_validation(client, auth_headers, seeded_db):
    group = _create_group(client, auth_headers, name="Validation Group")
    group_id = group.get_json()["id"]

    member = _create_member(
        client,
        auth_headers,
        email="valmember@test.ch",
        first_name="Val",
        last_name="Member",
    )
    member_id = member.get_json()["id"]

    client.post(
        f"/api/v1/groups/{group_id}/members/{member_id}",
        headers=auth_headers,
    )

    resp = client.patch(
        f"/api/v1/groups/{group_id}/members/{member_id}",
        json={"role": "invalid_role"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_update_member_role_not_in_group(client, auth_headers, seeded_db):
    group = _create_group(client, auth_headers, name="NotInGroup")
    group_id = group.get_json()["id"]

    member = _create_member(
        client,
        auth_headers,
        email="notmember@test.ch",
        first_name="Not",
        last_name="Member",
    )
    member_id = member.get_json()["id"]

    resp = client.patch(
        f"/api/v1/groups/{group_id}/members/{member_id}",
        json={"role": "leader"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ── Mailing list ─────────────────────────────────────────────────────────────


def test_mailing_list_returns_emails(client, auth_headers, seeded_db):
    group = _create_group(client, auth_headers, name="Mailing Group")
    group_id = group.get_json()["id"]

    member1 = _create_member(
        client,
        auth_headers,
        email="mail1@test.ch",
        first_name="Mail",
        last_name="One",
    )
    member2 = _create_member(
        client,
        auth_headers,
        email="mail2@test.ch",
        first_name="Mail",
        last_name="Two",
    )

    client.post(
        f"/api/v1/groups/{group_id}/members/{member1.get_json()['id']}",
        headers=auth_headers,
    )
    client.post(
        f"/api/v1/groups/{group_id}/members/{member2.get_json()['id']}",
        headers=auth_headers,
    )

    resp = client.get(
        f"/api/v1/groups/{group_id}/mailing-list",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["count"] == 2
    emails = [e["email"] for e in body["data"]]
    assert "mail1@test.ch" in emails
    assert "mail2@test.ch" in emails


def test_mailing_list_empty_group(client, auth_headers, seeded_db):
    group = _create_group(client, auth_headers, name="Empty Mailing")
    group_id = group.get_json()["id"]

    resp = client.get(
        f"/api/v1/groups/{group_id}/mailing-list",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["count"] == 0
    assert body["data"] == []


def test_mailing_list_group_not_found(client, auth_headers, seeded_db):
    resp = client.get(
        "/api/v1/groups/99999/mailing-list",
        headers=auth_headers,
    )
    assert resp.status_code == 404
