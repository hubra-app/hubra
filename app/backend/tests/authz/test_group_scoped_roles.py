"""A role can be held for one group only.

"Gruppenleitung for Jugend" lets a member edit the Jugend group and its
member list, and nothing in other groups.
"""

from hubra.core.models.group import Group

from tests.authz.conftest import _create_member_with_role, _login_member

GROUP_LEAD = [
    "groups.groups.read",
    "groups.groups.update",
    "groups.groups.add_member",
    "groups.groups.remove_member",
]


def _setup(db, seeded_db):
    tier = seeded_db["tier"]
    # The role exists with its permissions; its first holder is irrelevant.
    _, lead_role = _create_member_with_role(
        "someone@test.ch", "Gruppenleitung", tier.id, permission_keys=GROUP_LEAD
    )
    lead, _ = _create_member_with_role("lead@test.ch", "Plain", tier.id)
    jugend = Group(name="Jugend")
    senioren = Group(name="Senioren")
    db.session.add_all([jugend, senioren])
    db.session.commit()
    return lead_role, lead, jugend, senioren


def test_role_for_one_group(client, db, seeded_db):
    lead_role, lead, jugend, senioren = _setup(db, seeded_db)

    _login_member(client, "admin@test.ch")
    resp = client.post(
        f"/api/v1/roles/{lead_role.id}/scopes",
        json={"member_id": lead.id, "group_id": jugend.id},
    )
    assert resp.status_code == 201
    scope_id = resp.get_json()["id"]
    listed = client.get(f"/api/v1/roles/{lead_role.id}/scopes").get_json()
    assert [(s["member_id"], s["group_name"]) for s in listed] == [(lead.id, "Jugend")]
    rows = client.get("/api/v1/members/?pageSize=100").get_json()["data"]
    row = next(m for m in rows if m["id"] == lead.id)
    assert row["scoped_roles"] == [
        {"id": lead_role.id, "name": "Gruppenleitung", "group_id": jugend.id, "group": "Jugend"}
    ]

    _login_member(client, "lead@test.ch")
    perms = client.get("/api/v1/account/permissions").get_json()
    assert "groups.groups.update" in perms["scoped_permissions"][str(jugend.id)]
    assert "groups.groups.update" not in perms["permissions"]

    assert client.patch(f"/api/v1/groups/{jugend.id}", json={"description": "x"}).status_code == 200
    assert client.get(f"/api/v1/groups/{jugend.id}/members").status_code == 200
    resp = client.post(f"/api/v1/groups/{jugend.id}/members/{lead.id}")
    assert resp.status_code in (200, 201, 204)

    assert client.patch(f"/api/v1/groups/{senioren.id}", json={"description": "x"}).status_code == 403
    assert client.post(f"/api/v1/groups/{senioren.id}/members/{lead.id}").status_code == 403
    # Club-wide routes stay closed.
    assert client.post("/api/v1/groups/", json={"name": "Neu"}).status_code == 403

    _login_member(client, "admin@test.ch")
    resp = client.delete(f"/api/v1/roles/{lead_role.id}/scopes/{scope_id}")
    assert resp.status_code == 204

    _login_member(client, "lead@test.ch")
    assert client.patch(f"/api/v1/groups/{jugend.id}", json={"description": "y"}).status_code == 403


def test_admin_roles_are_club_wide(client, db, seeded_db):
    _, lead, jugend, _ = _setup(db, seeded_db)
    _login_member(client, "admin@test.ch")
    resp = client.post(
        f"/api/v1/roles/{seeded_db['role'].id}/scopes",
        json={"member_id": lead.id, "group_id": jugend.id},
    )
    assert resp.status_code == 400


def test_giving_a_group_role_needs_the_member_right(client, db, seeded_db):
    lead_role, lead, jugend, _ = _setup(db, seeded_db)
    # Holds the group rights club-wide, but may not change members.
    editor, _ = _create_member_with_role("group-editor@test.ch", "Plain2", seeded_db["tier"].id)
    editor.roles = [*editor.roles, lead_role]
    db.session.commit()
    _login_member(client, "group-editor@test.ch")
    resp = client.post(
        f"/api/v1/roles/{lead_role.id}/scopes",
        json={"member_id": lead.id, "group_id": jugend.id},
    )
    assert resp.status_code == 403
