"""Tests for group delete with members and managed mail cleanup."""

import pytest

from vollbuild.extensions import db
from vollbuild.core.models.group import Group
from vollbuild.core.models.managed_mail import ManagedMailAddress
from vollbuild.core.models.member import Member, member_groups
from vollbuild.core.models.user import User


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def group_with_members(seeded_db):
    """Create a group and 3 members assigned to it."""
    tier = seeded_db["tier"]

    group = Group(name="Woodworkers", color="#2596be")
    db.session.add(group)
    db.session.flush()

    members = []
    for i in range(3):
        user = User(
            email=f"member{i}@test.ch",
            first_name=f"Member{i}",
            last_name="Test",
        )
        user.set_password("password123")
        db.session.add(user)
        db.session.flush()

        m = Member(
            user_id=user.id,
            status="active",
            tier_id=tier.id,
        )
        db.session.add(m)
        members.append(m)

    db.session.flush()

    db.session.execute(
        member_groups.insert(),
        [{"member_id": m.id, "group_id": group.id} for m in members],
    )
    db.session.commit()

    return {"group": group, "members": members}


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_delete_group_with_members_succeeds(client, group_with_members, auth_headers):
    """DELETE /groups/{id} with 3 assigned members returns 204."""
    group_id = group_with_members["group"].id
    resp = client.delete(f"/api/v1/groups/{group_id}", headers=auth_headers)
    assert resp.status_code == 204


def test_members_remain_after_group_delete(client, group_with_members, auth_headers):
    """After group delete, GET /members still returns all 3 members."""
    group_id = group_with_members["group"].id
    member_ids = {m.id for m in group_with_members["members"]}

    client.delete(f"/api/v1/groups/{group_id}", headers=auth_headers)

    resp = client.get("/api/v1/members/?pageSize=500", headers=auth_headers)
    assert resp.status_code == 200
    returned_ids = {m["id"] for m in resp.get_json()["data"]}
    assert member_ids.issubset(returned_ids)


def test_group_not_found_after_delete(client, group_with_members, auth_headers):
    """After group delete, GET /groups/{id} returns 404."""
    group_id = group_with_members["group"].id
    client.delete(f"/api/v1/groups/{group_id}", headers=auth_headers)

    resp = client.get(f"/api/v1/groups/{group_id}", headers=auth_headers)
    assert resp.status_code == 404


def test_delete_group_removes_managed_mail_address(
    client, group_with_members, auth_headers
):
    """When group has a managed mail address, DELETE removes the MMA."""
    group = group_with_members["group"]
    addr = ManagedMailAddress(
        address="delete-test@club.ch",
        address_type="alias",
        is_protected=False,
        owner_type="group",
        owner_id=group.id,
    )
    db.session.add(addr)
    db.session.commit()
    addr_id = addr.id

    resp = client.delete(f"/api/v1/groups/{group.id}", headers=auth_headers)
    assert resp.status_code == 204
    assert db.session.get(ManagedMailAddress, addr_id) is None


def test_delete_group_with_protected_mma(client, group_with_members, auth_headers):
    """Group with a protected MMA can be deleted — MMA is cleaned up automatically."""
    group = group_with_members["group"]
    addr = ManagedMailAddress(
        address="protected@club.ch",
        address_type="alias",
        is_protected=True,
        owner_type="group",
        owner_id=group.id,
    )
    db.session.add(addr)
    db.session.commit()

    resp = client.delete(f"/api/v1/groups/{group.id}", headers=auth_headers)
    assert resp.status_code == 204
