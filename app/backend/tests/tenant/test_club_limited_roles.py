"""A platform role given for some clubs only: its holder sees and opens
those clubs (support) and nothing else on the platform."""

from unittest.mock import patch

import pytest
from sqlalchemy import select


@pytest.fixture
def support(client, db, seeded_db):
    """admin@test.ch is no superadmin; holds "Club support" (tenants.read,
    tenants.update, impersonate, audit.read) for Club A only."""
    from hubra.core.global_rbac_seed import seed_global_rbac
    from hubra.core.models.global_role import (
        GlobalPermission,
        GlobalRole,
        GlobalRolePermission,
        UserGlobalRole,
        UserGlobalRoleTenant,
    )
    from hubra.core.models.tenant import Tenant

    seed_global_rbac()
    a = Tenant(name="Club A", slug="club-a", status="active")
    b = Tenant(name="Club B", slug="club-b", status="active")
    db.session.add_all([a, b])
    role = GlobalRole(name="Club support", is_system=False)
    db.session.add(role)
    db.session.flush()
    for key in ("tenants.read", "tenants.update", "impersonate", "audit.read"):
        perm = db.session.scalar(
            select(GlobalPermission).where(GlobalPermission.key == key)
        )
        db.session.add(GlobalRolePermission(role_id=role.id, permission_id=perm.id))
    user = seeded_db["user"]
    user.is_superadmin = False
    link = UserGlobalRole(user_id=user.id, role_id=role.id)
    link.clubs = [UserGlobalRoleTenant(tenant_id=a.id)]
    db.session.add(link)
    db.session.commit()
    client.post(
        "/api/v1/auth/login", json={"email": "admin@test.ch", "password": "password123"}
    )
    return {"a": a.id, "b": b.id, "role": role, "user": user}


def test_sees_only_its_clubs(client, support):
    a, b = support["a"], support["b"]
    names = [
        t["slug"] for t in client.get("/api/v1/system/tenants").get_json()["tenants"]
    ]
    assert names == ["club-a"]
    health = client.get("/api/v1/system/tenants/health").get_json()
    assert [t["slug"] for t in health["tenants"]] == ["club-a"]
    assert client.get(f"/api/v1/system/tenants/{a}").status_code == 200
    assert client.get(f"/api/v1/system/tenants/{b}").status_code == 403


def test_may_open_its_club_as_a_member_only(client, support):
    a, b = support["a"], support["b"]
    with patch("hubra.core.tenant.context.set_search_path"):
        other = client.post(
            f"/api/v1/system/tenants/{b}/impersonate", json={"reason": "ticket"}
        )
        mine = client.post(
            f"/api/v1/system/tenants/{a}/impersonate", json={"reason": "ticket"}
        )
    assert other.get_json()["message"] == "Permission 'impersonate' required"
    # Past the rights check: the only member here is platform staff, who is
    # never opened, so that is where it ends.
    assert mine.get_json()["message"] == "Cannot impersonate platform staff"


def test_carries_club_rights_only(client, support):
    a = support["a"]
    # tenants.update and audit.read are in the role, but not for a club limit.
    assert (
        client.patch(f"/api/v1/system/tenants/{a}", json={"name": "X"}).status_code
        == 403
    )
    assert client.get("/api/v1/system/audit").status_code == 403
    perms = client.get("/api/v1/account/permissions").get_json()
    assert perms["global_permissions"] == []
    assert perms["club_permissions"] == {
        "impersonate": [a],
        "tenants.read": [a],
    }


def test_assign_a_role_for_some_clubs(client, db, seeded_db):
    from hubra.core.global_rbac_seed import seed_global_rbac
    from hubra.core.models.global_role import GlobalRole
    from hubra.core.models.tenant import Tenant
    from hubra.core.models.user import User

    seed_global_rbac()
    seeded_db["user"].is_superadmin = True
    club = Tenant(name="Club A", slug="club-a", status="active")
    helper = User(email="helper@test.ch", first_name="He", last_name="Lper")
    helper.set_password("helperpass123")
    db.session.add_all([club, helper])
    db.session.commit()
    role = db.session.scalar(select(GlobalRole).where(GlobalRole.name == "Support"))
    client.post(
        "/api/v1/auth/login", json={"email": "admin@test.ch", "password": "password123"}
    )

    bad = client.post(
        f"/api/v1/system/users/{helper.id}/roles",
        json={"role_id": role.id, "tenant_ids": [99999]},
    )
    assert bad.status_code == 404
    resp = client.post(
        f"/api/v1/system/users/{helper.id}/roles",
        json={"role_id": role.id, "tenant_ids": [club.id]},
    )
    assert resp.status_code == 201
    listed = client.get(f"/api/v1/system/users/{helper.id}/roles").get_json()
    assert listed["roles"] == [
        {"id": role.id, "name": "Support", "clubs": [{"id": club.id, "name": "Club A"}]}
    ]
