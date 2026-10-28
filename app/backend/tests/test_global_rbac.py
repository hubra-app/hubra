"""Tests for global RBAC — roles, permissions, and route guards."""

from sqlalchemy import select

from hubra.core.models.global_role import (
    GlobalPermission,
    GlobalRole,
    GlobalRolePermission,
    UserGlobalRole,
)
from hubra.core.models.user import User
from hubra.api.global_rbac_seed import seed_global_rbac


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_user(db, email: str, *, is_superadmin: bool = False) -> User:
    name_part = email.split("@")[0]
    user = User(
        email=email,
        first_name=name_part,
        last_name="",
        is_superadmin=is_superadmin,
    )
    user.set_password("VeryStrongPass123!")
    db.session.add(user)
    db.session.commit()
    return user


def _login(client, email: str):
    client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "VeryStrongPass123!"},
    )


def _assign_role(db, user: User, role_name: str):
    role = db.session.scalar(select(GlobalRole).where(GlobalRole.name == role_name))
    if role is None:
        role = GlobalRole(name=role_name, description="Test role")
        db.session.add(role)
        db.session.flush()
    db.session.add(UserGlobalRole(user_id=user.id, role_id=role.id))
    db.session.commit()


# ── Seed tests ────────────────────────────────────────────────────────────────


def test_seed_global_rbac_creates_permissions_and_roles(db):
    """seed_global_rbac creates all default permissions and roles."""
    seed_global_rbac()

    perm_count = db.session.query(GlobalPermission).count()
    assert perm_count == 11, f"Expected 11 permissions, got {perm_count}"

    role_count = db.session.query(GlobalRole).count()
    assert role_count == 4, f"Expected 4 roles, got {role_count}"

    superadmin = db.session.scalar(
        select(GlobalRole).where(GlobalRole.name == "Superadmin")
    )
    assert superadmin is not None
    assert superadmin.is_system is True

    perm_keys = set(
        db.session.execute(
            select(GlobalPermission.key)
            .join(
                GlobalRolePermission,
                GlobalRolePermission.permission_id == GlobalPermission.id,
            )
            .where(GlobalRolePermission.role_id == superadmin.id)
        )
        .scalars()
        .all()
    )
    assert "tenants.read" in perm_keys
    assert "roles.manage" in perm_keys


def test_seed_global_rbac_is_idempotent(db):
    """Running seed_global_rbac twice doesn't create duplicates."""
    seed_global_rbac()
    seed_global_rbac()

    assert db.session.query(GlobalPermission).count() == 11
    assert db.session.query(GlobalRole).count() == 4


# ── Permission decorator tests ────────────────────────────────────────────────


def test_superadmin_bypasses_permission_checks(client, seeded_db, db):
    """Superadmin can access routes even without global role assignments."""
    _make_user(db, "superadmin@test.ch", is_superadmin=True)
    _login(client, "superadmin@test.ch")

    resp = client.get("/api/v1/system/tenants")
    assert resp.status_code == 200


def test_user_without_global_role_gets_403(client, seeded_db, db):
    """A regular user (no global roles) gets 403 on permission-gated routes."""
    seed_global_rbac()
    _make_user(db, "noperm@test.ch")
    _login(client, "noperm@test.ch")

    resp = client.get("/api/v1/system/tenants")
    assert resp.status_code == 403


def test_manager_role_can_read_tenants(client, seeded_db, db):
    """User with Manager role can read tenants but not delete them."""
    seed_global_rbac()
    user = _make_user(db, "manager@test.ch")
    _assign_role(db, user, "Manager")
    _login(client, "manager@test.ch")

    resp = client.get("/api/v1/system/tenants")
    assert resp.status_code == 200

    # Manager should NOT be able to delete tenants
    from hubra.core.models.tenant import Tenant

    tenant = Tenant(name="Test", slug="test-manager", plan="starter")
    db.session.add(tenant)
    db.session.commit()

    resp = client.delete(f"/api/v1/system/tenants/{tenant.id}")
    assert resp.status_code == 403


def test_support_role_can_impersonate_but_not_approve(client, seeded_db, db):
    """User with Support role can access impersonate endpoint but not approve requests."""
    seed_global_rbac()
    user = _make_user(db, "support@test.ch")
    _assign_role(db, user, "Support")
    _login(client, "support@test.ch")

    # Support can read tenants
    resp = client.get("/api/v1/system/tenants")
    assert resp.status_code == 200

    # Support cannot approve tenant requests
    resp = client.post("/api/v1/system/tenant-requests/1/approve")
    assert resp.status_code == 403


def test_requester_role_cannot_read_tenants(client, seeded_db, db):
    """User with Requester role (no permissions) gets 403 on /tenants."""
    seed_global_rbac()
    user = _make_user(db, "requester@test.ch")
    _assign_role(db, user, "Requester")
    _login(client, "requester@test.ch")

    resp = client.get("/api/v1/system/tenants")
    assert resp.status_code == 403


# ── /account/permissions includes global_permissions ─────────────────────────


def test_permissions_endpoint_includes_global_permissions(client, seeded_db, db):
    """/account/permissions returns global_permissions and global_roles."""
    seed_global_rbac()
    user = _make_user(db, "globperm@test.ch")
    _assign_role(db, user, "Manager")
    _login(client, "globperm@test.ch")

    resp = client.get("/api/v1/account/permissions")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "global_permissions" in body
    assert "global_roles" in body
    assert "Manager" in body["global_roles"]
    assert "tenants.read" in body["global_permissions"]


def test_permissions_endpoint_superadmin_gets_wildcard(client, seeded_db, db):
    """Superadmin gets global_permissions=['*']."""  # noqa: F841
    _make_user(db, "sa-perm@test.ch", is_superadmin=True)
    _login(client, "sa-perm@test.ch")

    resp = client.get("/api/v1/account/permissions")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["global_permissions"] == ["*"]
