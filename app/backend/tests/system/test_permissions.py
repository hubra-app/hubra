"""Integration tests for M005/S02: permission audit and system permissions endpoint.

Verifies:
- GET /api/v1/system/permissions requires auth (401) and admin role (403).
- Admin receives a list with method/path/permission keys.
- Inventory entries use 'View inventory' / 'Manage inventory'; old wrong strings absent.
- Member with 'View inventory' can GET /inventory/ but gets 403 on POST.
"""

import pytest
from sqlalchemy import select

from hubra.core.extensions import db as _db
from hubra.core.models.member import Member
from hubra.core.models.role import Role, RolePermission, Permission
from hubra.core.models.user import User

SYSTEM_PERMISSIONS = "/api/v1/system/permissions"
INVENTORY = "/api/v1/inventory/"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def member_auth_headers(client, seeded_db):
    """Create a Member role with inventory read permission, create a member, log in."""
    tier = seeded_db["tier"]

    member_role = Role(name="Member", is_default=False)
    _db.session.add(member_role)
    _db.session.flush()

    # Create Permission rows and grant them to the member role
    for key in [
        "members.members.read",
        "finance.overview.read",
        "groups.groups.read",
        "inventory.items.read",
    ]:
        perm = _db.session.scalar(select(Permission).where(Permission.key == key))
        if perm is None:
            perm = Permission(
                key=key,
                display_name=key,
                resource=key.split(".")[1] if "." in key else key,
                action=key.split(".")[2]
                if "." in key and len(key.split(".")) > 2
                else key,
                blueprint=key.split(".")[0] if "." in key else "",
            )
            _db.session.add(perm)
            _db.session.flush()
        _db.session.add(RolePermission(role_id=member_role.id, permission_id=perm.id))

    member_user = User(
        email="member@test.ch",
        first_name="Regular",
        last_name="Member",
    )
    member_user.set_password("password123")
    _db.session.add(member_user)
    _db.session.flush()

    member = Member(
        user_id=member_user.id,
        status="active",
        tier_id=tier.id,
    )
    member.roles = [member_role]
    _db.session.add(member)
    _db.session.commit()

    client.post(
        "/api/v1/auth/login",
        json={
            "email": "member@test.ch",
            "password": "password123",
        },
    )
    return {}


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_system_permissions_requires_auth(client, seeded_db):
    """GET /api/v1/system/permissions with no token → 401."""
    resp = client.get(SYSTEM_PERMISSIONS)
    assert resp.status_code == 401


def test_system_permissions_requires_admin(client, seeded_db, member_auth_headers):
    """GET /api/v1/system/permissions with member token → 403."""
    resp = client.get(SYSTEM_PERMISSIONS, headers=member_auth_headers)
    assert resp.status_code == 403


def test_system_permissions_returns_list(client, seeded_db, auth_headers):
    """GET /api/v1/system/permissions with admin token → 200, list of dicts with correct keys."""
    resp = client.get(SYSTEM_PERMISSIONS, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) > 0
    for entry in data:
        assert "method" in entry
        assert "path" in entry
        assert "key" in entry


def test_system_permissions_inventory_uses_correct_strings(
    client, seeded_db, auth_headers
):
    """Inventory entries must use 'View inventory'/'Manage inventory' keys; old wrong strings absent."""
    resp = client.get(SYSTEM_PERMISSIONS, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()

    inventory_entries = [e for e in data if "/inventory" in e["path"]]
    assert len(inventory_entries) > 0, "No inventory entries found in permissions list"

    permissions_on_inventory = {e["key"] for e in inventory_entries}
    assert "inventory.items.read" in permissions_on_inventory
    assert "inventory.items.create" in permissions_on_inventory
    assert "groups.groups.read" not in permissions_on_inventory
    assert "events.events.read" not in permissions_on_inventory


def test_member_can_view_inventory(client, seeded_db, member_auth_headers):
    """Member with 'View inventory' permission can GET /api/v1/inventory/ → 200."""
    resp = client.get(INVENTORY, headers=member_auth_headers)
    assert resp.status_code == 200


def test_member_cannot_create_inventory(client, seeded_db, member_auth_headers):
    """Member without 'Manage inventory' gets 403 on POST /api/v1/inventory/."""
    resp = client.post(
        INVENTORY,
        json={"name": "X", "category": "Tool"},
        headers=member_auth_headers,
    )
    assert resp.status_code == 403
