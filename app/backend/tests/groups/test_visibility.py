"""Private groups are seen only by their members, their lead and group managers."""

from __future__ import annotations

import pytest

from hubra.core.extensions import db as _db
from hubra.core.models.group import Group
from hubra.core.models.member import Member
from hubra.core.models.role import Permission, Role, RolePermission
from hubra.core.models.user import User


def _role(name: str, keys: list[str]) -> Role:
    role = Role(name=name, is_default=False, is_admin=False)
    _db.session.add(role)
    _db.session.flush()
    for key in keys:
        perm = _db.session.query(Permission).filter_by(key=key).first()
        if perm is None:
            blueprint, resource, action = key.split(".")
            perm = Permission(
                key=key, display_name=key, resource=resource, action=action, blueprint=blueprint
            )
            _db.session.add(perm)
            _db.session.flush()
        _db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    return role


def _member(seeded_db, email: str, role: Role) -> Member:
    user = User(email=email, first_name="Vis", last_name="Test", private_email_verified=True)
    user.set_password("password123")
    _db.session.add(user)
    _db.session.flush()
    member = Member(user_id=user.id, status="active", tier_id=seeded_db["tier"].id)
    member.roles = [role]
    _db.session.add(member)
    _db.session.flush()
    return member


def _login(client, email: str) -> None:
    client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})


@pytest.fixture
def setup(seeded_db):
    reader = _role("GroupReader", ["groups.groups.read"])
    manager = _role("GroupManager", ["groups.groups.read", "groups.groups.update"])
    outsider = _member(seeded_db, "outsider@test.ch", reader)
    insider = _member(seeded_db, "insider@test.ch", reader)
    lead = _member(seeded_db, "lead@test.ch", reader)
    _member(seeded_db, "manager@test.ch", manager)
    open_group = Group(name="Climbing", visibility="open")
    visible = Group(name="Board", type="board")
    private = Group(name="Selection", type="team", visibility="private", lead_id=lead.id)
    _db.session.add_all([open_group, visible, private])
    _db.session.flush()
    private.members.append(insider)
    _db.session.commit()
    return {"outsider": outsider, "private": private}


def _names(client) -> list[str]:
    resp = client.get("/api/v1/groups/")
    assert resp.status_code == 200
    return sorted(g["name"] for g in resp.get_json())


def test_outsider_does_not_see_a_private_group(client, setup):
    _login(client, "outsider@test.ch")
    assert _names(client) == ["Board", "Climbing"]
    gid = setup["private"].id
    assert client.get(f"/api/v1/groups/{gid}").status_code == 404
    assert client.get(f"/api/v1/groups/{gid}/members").status_code == 404


@pytest.mark.parametrize("email", ["insider@test.ch", "lead@test.ch", "manager@test.ch"])
def test_members_lead_and_managers_see_it(client, setup, email):
    _login(client, email)
    assert "Selection" in _names(client)
    gid = setup["private"].id
    assert client.get(f"/api/v1/groups/{gid}").status_code == 200
    assert client.get(f"/api/v1/groups/{gid}/members").status_code == 200


def test_admin_sees_every_group(client, auth_headers, setup):
    assert "Selection" in _names(client)


def test_only_open_groups_can_be_joined(client, setup):
    _login(client, "outsider@test.ch")
    assert [g["name"] for g in client.get("/api/v1/groups/joinable").get_json()] == ["Climbing"]
    assert client.post(f"/api/v1/groups/{setup['private'].id}/join").status_code == 403


def test_visibility_defaults_to_visible(client, auth_headers, seeded_db):
    resp = client.post("/api/v1/groups/", json={"name": "Neu"})
    assert resp.status_code == 201
    assert resp.get_json()["visibility"] == "visible"
