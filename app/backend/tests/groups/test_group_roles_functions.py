"""Groups give roles, functions held per group, default and tier groups
(docs/roles.md, "Groups")."""

import pytest
from flask import g
from sqlalchemy import select

from tests.settings.test_settings_kv import _login, _make_role_and_member


def _fresh(db):
    db.session.expire_all()
    for key in ("_function_roles", "_group_roles", "_scoped_keys"):
        g.pop(key, None)


def _role(db, name, keys=(), is_admin=False):
    from hubra.core.models.role import Permission, Role, RolePermission

    role = Role(name=name, is_admin=is_admin)
    db.session.add(role)
    db.session.flush()
    for key in keys:
        perm = db.session.scalar(select(Permission).where(Permission.key == key))
        db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    db.session.commit()
    return role


@pytest.fixture
def club(app, db, seeded_db):
    app.test_cli_runner().invoke(args=["sync-permissions"])
    tier = seeded_db["tier"]
    anna = _make_role_and_member(db, tier, name="Anna", permission_keys=[])
    inventory = _role(db, "Inventar", ["groups.groups.read", "events.events.create"])
    return {"anna": anna, "inventory": inventory, "tier": tier}


# ── Groups give roles ─────────────────────────────────────────────────────────


def test_a_group_gives_its_roles_while_you_are_in_it(
    app, client, db, club, auth_headers
):
    from hubra.core.permissions import held_roles, member_has_permission

    r = client.post(
        "/api/v1/groups/",
        json={"name": "Werkstatt", "role_ids": [club["inventory"].id]},
    )
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body["role_ids"] == [club["inventory"].id]
    assert body["roles"] == [{"id": club["inventory"].id, "name": "Inventar"}]

    anna = club["anna"]
    with app.test_request_context():
        assert not member_has_permission(anna, "events.events.create")

    url = f"/api/v1/groups/{body['id']}/members/{anna.id}"
    assert client.post(url).status_code == 204
    with app.test_request_context():
        _fresh(db)
        assert "Inventar" in {r.name for r in held_roles(anna)}
        assert member_has_permission(anna, "events.events.create")

    # The members list shows where the role comes from, and the role filter
    # finds her.
    m = client.get(f"/api/v1/members/{anna.id}").get_json()
    assert m["group_roles"] == [
        {
            "id": club["inventory"].id,
            "name": "Inventar",
            "group_id": body["id"],
            "group": "Werkstatt",
        }
    ]
    found = client.get(f"/api/v1/members/?role_id={club['inventory'].id}").get_json()[
        "data"
    ]
    assert anna.id in [x["id"] for x in found]
    counts = {
        x["id"]: x.get("member_count") for x in client.get("/api/v1/roles/").get_json()
    }
    assert counts.get(club["inventory"].id) == 1

    assert client.delete(url).status_code == 204
    with app.test_request_context():
        _fresh(db)
        assert not member_has_permission(anna, "events.events.create")


def test_a_group_never_gives_an_admin_role(client, club, seeded_db, auth_headers):
    r = client.post(
        "/api/v1/groups/",
        json={"name": "Chefs", "role_ids": [seeded_db["role"].id]},
    )
    assert r.status_code == 400


def test_an_open_group_gives_no_roles(client, club, auth_headers):
    r = client.post(
        "/api/v1/groups/",
        json={
            "name": "Offen",
            "visibility": "open",
            "role_ids": [club["inventory"].id],
        },
    )
    assert r.status_code == 400
    gid = client.post(
        "/api/v1/groups/", json={"name": "Zu", "role_ids": [club["inventory"].id]}
    ).get_json()["id"]
    assert (
        client.patch(f"/api/v1/groups/{gid}", json={"visibility": "open"}).status_code
        == 400
    )


def test_a_leader_cannot_hand_out_roles_they_lack(
    app, client, db, club, seeded_db, auth_headers
):
    from hubra.core.models.group import Group

    lead = _make_role_and_member(db, seeded_db["tier"], name="Lea", permission_keys=[])
    group = Group(name="Jugend", lead_id=lead.id)
    group.roles = [club["inventory"]]
    db.session.add(group)
    db.session.commit()
    _login(client, "lea@test.ch")
    r = client.post(f"/api/v1/groups/{group.id}/members/{club['anna'].id}")
    assert r.status_code == 403
    assert "BEYOND_OWN_PERMISSIONS" in str(r.get_json())


def test_member_form_group_change_checks_the_roles(app, client, db, club, seeded_db):
    from hubra.core.models.group import Group

    clerk = _make_role_and_member(
        db,
        seeded_db["tier"],
        name="Clerk",
        permission_keys=["members.members.update", "members.members.read"],
    )
    group = Group(name="Kasse")
    group.roles = [club["inventory"]]
    db.session.add(group)
    db.session.commit()
    _login(client, "clerk@test.ch")
    r = client.patch(
        f"/api/v1/members/{club['anna'].id}", json={"group_ids": [group.id]}
    )
    assert r.status_code == 403, r.get_json()
    del clerk


# ── Group functions ───────────────────────────────────────────────────────────


def test_a_group_function_gives_its_roles_in_its_group_only(
    app, client, db, club, auth_headers
):
    from hubra.core.permissions import held_roles, scoped_permission_keys

    jugend = client.post("/api/v1/groups/", json={"name": "Jugend"}).get_json()["id"]
    senioren = client.post("/api/v1/groups/", json={"name": "Senioren"}).get_json()[
        "id"
    ]
    r = client.post(
        "/api/v1/functions/",
        json={
            "name": "Trainer/in",
            "perGroup": True,
            "grantsRoleIds": [club["inventory"].id],
        },
    )
    assert r.status_code == 201, r.get_json()
    fn = r.get_json()
    assert fn["perGroup"] is True

    anna = club["anna"]
    holders = f"/api/v1/functions/{fn['id']}/holders"
    # A group function needs the group.
    assert client.post(holders, json={"memberId": anna.id}).status_code == 400
    assert (
        client.post(holders, json={"memberId": anna.id, "groupId": jugend}).status_code
        == 201
    )
    # Once per group, but in several groups.
    assert (
        client.post(holders, json={"memberId": anna.id, "groupId": jugend}).status_code
        == 409
    )
    assert (
        client.post(
            holders, json={"memberId": anna.id, "groupId": senioren}
        ).status_code
        == 201
    )

    with app.test_request_context():
        _fresh(db)
        # Not a club-wide role ...
        assert "Inventar" not in {r.name for r in held_roles(anna)}
        # ... but in both groups.
        scoped = scoped_permission_keys(anna)
        assert "events.events.create" in scoped[jugend]
        assert "events.events.create" in scoped[senioren]

    body = client.get(f"/api/v1/groups/{jugend}").get_json()
    assert [(f["function_name"], f["member_id"]) for f in body["functions"]] == [
        ("Trainer/in", anna.id)
    ]
    listed = client.get(f"/api/v1/functions/{fn['id']}").get_json()["holders"]
    assert sorted(h["groupName"] for h in listed) == ["Jugend", "Senioren"]

    r = client.delete(f"{holders}/{anna.id}?groupId={jugend}")
    assert r.status_code == 200
    with app.test_request_context():
        _fresh(db)
        assert jugend not in scoped_permission_keys(anna)
        assert senioren in scoped_permission_keys(anna)

    # A club function has no group.
    club_fn = client.post("/api/v1/functions/", json={"name": "Revisor/in"}).get_json()
    r = client.post(
        f"/api/v1/functions/{club_fn['id']}/holders",
        json={"memberId": anna.id, "groupId": jugend},
    )
    assert r.status_code == 400


def test_a_group_function_cannot_give_admin(client, club, seeded_db, auth_headers):
    r = client.post(
        "/api/v1/functions/",
        json={
            "name": "Chef/in",
            "perGroup": True,
            "grantsRoleIds": [seeded_db["role"].id],
        },
    )
    assert r.status_code == 400


def test_switching_a_function_with_holders_is_refused(client, club, auth_headers):
    fn = client.post("/api/v1/functions/", json={"name": "Revisor/in"}).get_json()
    client.post(
        f"/api/v1/functions/{fn['id']}/holders", json={"memberId": club["anna"].id}
    )
    r = client.patch(f"/api/v1/functions/{fn['id']}", json={"perGroup": True})
    assert r.status_code == 409


# ── Default groups and tier groups ────────────────────────────────────────────


def test_new_members_join_the_default_and_tier_groups(
    app, client, db, club, seeded_db, auth_headers
):
    from hubra.core.models.member import Member, MembershipTier
    from tests.helpers import add_member

    alle = client.post(
        "/api/v1/groups/", json={"name": "Alle", "is_default": True}
    ).get_json()
    assert alle["is_default"] is True
    junior = MembershipTier(name="Junior", price_chf=20, color="#123456")
    db.session.add(junior)
    db.session.commit()
    jugend = client.post(
        "/api/v1/groups/", json={"name": "Jugend", "tier_ids": [junior.id]}
    ).get_json()
    assert jugend["tier_ids"] == [junior.id]

    new = add_member(
        client,
        {},
        email="neu@test.ch",
        first_name="Neu",
        last_name="Mitglied",
        tier_id=junior.id,
    ).get_json()
    assert sorted(new["group_ids"]) == sorted([alle["id"], jugend["id"]])

    # Changing the tier moves the tier groups, the default group stays.
    erwachsen = client.post("/api/v1/groups/", json={"name": "Erwachsene"}).get_json()
    r = client.patch(
        f"/api/v1/tiers/{seeded_db['tier'].id}", json={"group_ids": [erwachsen["id"]]}
    )
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["group_ids"] == [erwachsen["id"]]
    r = client.patch(
        f"/api/v1/members/{new['id']}", json={"tier_id": seeded_db["tier"].id}
    )
    assert r.status_code == 200, r.get_json()
    db.session.expire_all()
    member = db.session.get(Member, new["id"])
    assert sorted(g.id for g in member.groups) == sorted([alle["id"], erwachsen["id"]])
    del MembershipTier


def test_linking_a_tier_adds_its_members_now(client, db, club, seeded_db, auth_headers):
    from hubra.core.models.member import Member

    g_id = client.post(
        "/api/v1/groups/", json={"name": "Maker", "tier_ids": [seeded_db["tier"].id]}
    ).get_json()["id"]
    db.session.expire_all()
    anna = db.session.get(Member, club["anna"].id)
    assert g_id in [g.id for g in anna.groups]


def test_deleting_a_group_unlinks_roles_tiers_and_functions(
    client, db, club, seeded_db, auth_headers
):
    from hubra.core.models.function import FunctionHolder
    from hubra.core.models.group import group_roles, tier_groups

    gid = client.post(
        "/api/v1/groups/",
        json={
            "name": "Weg",
            "role_ids": [club["inventory"].id],
            "tier_ids": [seeded_db["tier"].id],
        },
    ).get_json()["id"]
    fn = client.post(
        "/api/v1/functions/", json={"name": "Leiter/in", "perGroup": True}
    ).get_json()
    client.post(
        f"/api/v1/functions/{fn['id']}/holders",
        json={"memberId": club["anna"].id, "groupId": gid},
    )
    assert client.delete(f"/api/v1/groups/{gid}").status_code == 204
    assert (
        db.session.execute(
            select(group_roles).where(group_roles.c.group_id == gid)
        ).first()
        is None
    )
    assert (
        db.session.execute(
            select(tier_groups).where(tier_groups.c.group_id == gid)
        ).first()
        is None
    )
    assert (
        db.session.scalar(select(FunctionHolder).where(FunctionHolder.group_id == gid))
        is None
    )
