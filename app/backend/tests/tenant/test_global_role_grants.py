"""Platform staff with roles.manage give only platform rights they hold
themselves, so roles.manage alone is no way to superadmin."""

import pytest


@pytest.fixture
def role_manager(client, db, seeded_db):
    """admin@test.ch on the platform with roles.manage only (no superadmin),
    and a role "Deleter" granting tenants.delete."""
    from sqlalchemy import select

    from hubra.api.global_rbac_seed import seed_global_rbac
    from hubra.core.models.global_role import (
        GlobalPermission,
        GlobalRole,
        GlobalRolePermission,
        UserGlobalRole,
    )

    seed_global_rbac()

    def _role(name, key):
        role = GlobalRole(name=name, is_system=False)
        db.session.add(role)
        db.session.flush()
        perm = db.session.scalar(
            select(GlobalPermission).where(GlobalPermission.key == key)
        )
        db.session.add(GlobalRolePermission(role_id=role.id, permission_id=perm.id))
        return role

    manager = _role("Role managers", "roles.manage")
    deleter = _role("Deleter", "tenants.delete")
    user = seeded_db["user"]
    user.is_superadmin = False
    db.session.add(UserGlobalRole(user_id=user.id, role_id=manager.id))
    db.session.commit()
    client.post(
        "/api/v1/auth/login", json={"email": "admin@test.ch", "password": "password123"}
    )
    return {"user": user, "manager": manager, "deleter": deleter}


def test_a_role_with_rights_beyond_ones_own_is_refused(client, role_manager):
    resp = client.post(
        "/api/v1/system/global-roles",
        json={"name": "All", "permissions": ["roles.manage", "tenants.delete"]},
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"] == "BEYOND_OWN_PERMISSIONS"

    ok = client.post(
        "/api/v1/system/global-roles",
        json={"name": "Helpers", "permissions": ["roles.manage"]},
    )
    assert ok.status_code == 201


def test_adding_a_right_one_lacks_to_a_role_is_refused(client, role_manager):
    manager = role_manager["manager"]
    resp = client.patch(
        f"/api/v1/system/global-roles/{manager.id}",
        json={"permissions": ["roles.manage", "tenants.delete"]},
    )
    assert resp.status_code == 403
    # Sending a role's rights back unchanged is fine, even ones one lacks.
    deleter = role_manager["deleter"]
    same = client.patch(
        f"/api/v1/system/global-roles/{deleter.id}",
        json={"permissions": ["tenants.delete"], "description": "Cleans up"},
    )
    assert same.status_code == 200


def test_giving_or_taking_a_role_with_more_reach_is_refused(client, role_manager):
    user = role_manager["user"]
    deleter = role_manager["deleter"]
    resp = client.post(
        f"/api/v1/system/users/{user.id}/roles", json={"role_id": deleter.id}
    )
    assert resp.status_code == 403

    from hubra.core.extensions import db
    from hubra.core.models.global_role import UserGlobalRole
    from hubra.core.models.user import User

    other = User(email="boss@test.ch", first_name="B", last_name="S")
    other.set_password("password123")
    db.session.add(other)
    db.session.flush()
    db.session.add(UserGlobalRole(user_id=other.id, role_id=deleter.id))
    db.session.commit()
    taken = client.delete(f"/api/v1/system/users/{other.id}/roles/{deleter.id}")
    assert taken.status_code == 403
