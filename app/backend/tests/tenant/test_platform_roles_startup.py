"""Platform roles exist after a normal start, and manage can pick permissions.

Before, the platform permission catalogue and the default platform roles were
only written by ``flask seed-global-rbac``, which no deployment ran: manage ›
Rollen showed no roles and an empty permission list.
"""

from sqlalchemy import select

from hubra.api.global_rbac_seed import seed_global_rbac
from hubra.core.models.global_role import (
    GlobalPermission,
    GlobalRole,
    GlobalRolePermission,
)

DEFAULT_ROLES = {"Platform admin", "Manager", "Support", "Read-only", "Requester"}


def _role_keys(db, name):
    role = db.session.scalar(select(GlobalRole).where(GlobalRole.name == name))
    return set(
        db.session.scalars(
            select(GlobalPermission.key)
            .join(GlobalRolePermission)
            .where(GlobalRolePermission.role_id == role.id)
        )
    )


def _login_superadmin(client, db, seeded_db):
    seeded_db["user"].is_superadmin = True
    db.session.commit()
    client.post(
        "/api/v1/auth/login", json={"email": "admin@test.ch", "password": "password123"}
    )


def test_startup_sync_seeds_platform_permissions_and_roles(app, db):
    assert db.session.query(GlobalPermission).count() == 0
    result = app.test_cli_runner().invoke(args=["sync-permissions"])
    assert result.exit_code == 0, result.output

    assert db.session.query(GlobalPermission).count() > 0
    names = set(db.session.scalars(select(GlobalRole.name)))
    assert DEFAULT_ROLES <= names
    assert "tenants.read" in _role_keys(db, "Read-only")
    assert not {"tenants.update", "impersonate"} & _role_keys(db, "Read-only")


def test_manage_lists_permissions_and_roles(app, client, db, seeded_db):
    app.test_cli_runner().invoke(args=["sync-permissions"])
    _login_superadmin(client, db, seeded_db)

    resp = client.get("/api/v1/platform/system/global-permissions")
    assert resp.status_code == 200
    keys = {p["key"] for p in resp.get_json()["permissions"]}
    assert {"tenants.read", "roles.manage", "audit.read"} <= keys
    # Superadmin-only rights are never offered for a role.
    assert "plugins.manage" not in keys

    resp = client.get("/api/v1/platform/system/global-roles")
    assert DEFAULT_ROLES <= {r["name"] for r in resp.get_json()["roles"]}


def test_permissions_can_be_given_to_a_new_role(app, client, db, seeded_db):
    app.test_cli_runner().invoke(args=["sync-permissions"])
    _login_superadmin(client, db, seeded_db)

    resp = client.post(
        "/api/v1/platform/system/global-roles",
        json={"name": "Auditors", "permissions": ["audit.read", "tenants.read"]},
    )
    assert resp.status_code == 201, resp.get_json()
    role_id = resp.get_json()["role"]["id"]
    assert _role_keys(db, "Auditors") == {"audit.read", "tenants.read"}

    resp = client.patch(
        f"/api/v1/platform/system/global-roles/{role_id}",
        json={"permissions": ["audit.read"]},
    )
    assert resp.status_code == 200
    assert resp.get_json()["role"]["permissions"] == ["audit.read"]


def test_restart_keeps_changes_to_default_roles(db):
    seed_global_rbac()
    support = db.session.scalar(select(GlobalRole).where(GlobalRole.name == "Support"))
    db.session.query(GlobalRolePermission).filter(
        GlobalRolePermission.role_id == support.id
    ).delete()
    db.session.commit()

    seed_global_rbac()  # next start
    assert _role_keys(db, "Support") == set()


def test_restart_keeps_platform_admin_complete(db):
    seed_global_rbac()
    admin = db.session.scalar(
        select(GlobalRole).where(GlobalRole.name == "Platform admin")
    )
    db.session.query(GlobalRolePermission).filter(
        GlobalRolePermission.role_id == admin.id
    ).delete()
    db.session.commit()

    seed_global_rbac()
    assert "roles.manage" in _role_keys(db, "Platform admin")


def test_restart_does_not_duplicate_roles(db):
    seed_global_rbac()
    seed_global_rbac()
    for name in DEFAULT_ROLES:
        assert db.session.query(GlobalRole).filter(GlobalRole.name == name).count() == 1
