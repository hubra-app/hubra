"""Tests for Owner invariant — every tenant must have >=1 Owner at all times.

Tests that:
  - Cannot disable the last Owner
  - Cannot archive the last Owner
  - Cannot remove the Owner role from the last Owner via PATCH member
  - Can disable/archive a non-Owner member
  - Can remove Owner role when there are multiple Owners
"""

from vollbuild.core.extensions import db
from vollbuild.core.models.member import Member
from vollbuild.core.models.role import Role
from vollbuild.core.models.user import User


def _create_member(db, tier, roles=None, email="test@example.com"):
    """Helper: create a User + Member with the given roles."""
    user = User(
        email=email,
        first_name="Test",
        last_name="Member",
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()

    member = Member(
        user_id=user.id,
        status="active",
        tier_id=tier.id,
    )
    if roles:
        member.roles = list(roles)
    db.session.add(member)
    db.session.flush()
    return member


def test_cannot_disable_last_owner(client, seeded_db, auth_headers):
    """Disable the last Owner → 409."""
    tier = seeded_db["tier"]
    owner_role = seeded_db["owner_role"]

    # Create a separate owner (not the admin who is acting)
    owner = _create_member(db, tier, roles=[owner_role], email="owner@test.ch")
    db.session.commit()

    resp = client.post(
        f"/api/v1/members/{owner.id}/disable",
        headers=auth_headers,
    )
    assert resp.status_code == 409


def test_cannot_archive_last_owner(client, seeded_db, auth_headers):
    """Archive the last Owner → 409."""
    tier = seeded_db["tier"]
    owner_role = seeded_db["owner_role"]
    admin_role = seeded_db["role"]

    # Keep admin role but remove Owner from admin so test owner is the only one
    admin = seeded_db["admin"]
    admin.roles = [admin_role]
    db.session.flush()

    owner = _create_member(db, tier, roles=[owner_role], email="owner2@test.ch")
    db.session.commit()

    resp = client.post(
        f"/api/v1/members/{owner.id}/archive",
        headers=auth_headers,
    )
    assert resp.status_code == 409


def test_can_disable_non_owner(client, seeded_db, auth_headers):
    """Disable a non-Owner member → 200."""
    tier = seeded_db["tier"]
    member_role = Role(name="Member", is_system=True, is_default=True)
    db.session.add(member_role)
    db.session.flush()

    member = _create_member(db, tier, roles=[member_role], email="regular@test.ch")
    db.session.commit()

    resp = client.post(
        f"/api/v1/members/{member.id}/disable",
        headers=auth_headers,
    )
    assert resp.status_code == 200


def test_cannot_remove_owner_role_from_last_owner(client, seeded_db, auth_headers):
    """PATCH member removing Owner role from last Owner → 409."""
    tier = seeded_db["tier"]
    owner_role = seeded_db["owner_role"]
    admin_role = seeded_db["role"]

    # Keep admin role but remove Owner from admin so test owner is the only one
    admin = seeded_db["admin"]
    admin.roles = [admin_role]
    db.session.flush()

    owner = _create_member(db, tier, roles=[owner_role], email="owner3@test.ch")
    db.session.commit()

    member_role = Role(name="Member2", is_system=True)
    db.session.add(member_role)
    db.session.flush()

    resp = client.patch(
        f"/api/v1/members/{owner.id}",
        json={"role_ids": [member_role.id]},
        headers=auth_headers,
    )
    assert resp.status_code == 409


def test_can_remove_owner_role_when_multiple_owners(client, seeded_db, auth_headers):
    """When 2+ Owners, removing Owner from one → 200."""
    tier = seeded_db["tier"]
    owner_role = seeded_db["owner_role"]

    # First owner is the seeded admin
    admin = seeded_db["admin"]
    admin.roles = [owner_role]
    db.session.flush()

    # Create a second owner
    second_owner = _create_member(db, tier, roles=[owner_role], email="owner2@test.ch")
    db.session.commit()

    # Remove Owner role from the second owner
    member_role = Role(name="Member3", is_system=True)
    db.session.add(member_role)
    db.session.flush()

    resp = client.patch(
        f"/api/v1/members/{second_owner.id}",
        json={"role_ids": [member_role.id]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
