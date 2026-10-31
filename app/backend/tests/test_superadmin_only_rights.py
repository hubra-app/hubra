"""Plugins and backups are for the superadmin flag only: plugin code runs in
the backend and a restore overwrites every club, so no platform role carries
those rights, whatever its permission rows say."""

from sqlalchemy import select


def test_a_role_cannot_carry_plugins_or_backups(client, seeded_db, db):
    from hubra.api.global_rbac_seed import seed_global_rbac
    from hubra.core.models.global_role import (
        GlobalPermission,
        GlobalRole,
        GlobalRolePermission,
        UserGlobalRole,
    )
    from hubra.core.models.user import User

    seed_global_rbac()
    # A role that still links the rights (as the old "Superadmin" role did).
    role = db.session.scalar(select(GlobalRole).where(GlobalRole.name == "Platform admin"))
    for key in ("plugins.manage", "backups.manage"):
        perm = db.session.scalar(select(GlobalPermission).where(GlobalPermission.key == key))
        db.session.add(GlobalRolePermission(role_id=role.id, permission_id=perm.id))
    staff = User(email="staff@test.ch", first_name="S", last_name="T")
    staff.set_password("password123")
    db.session.add(staff)
    db.session.flush()
    db.session.add(UserGlobalRole(user_id=staff.id, role_id=role.id))
    db.session.commit()

    client.post("/api/v1/auth/login", json={"email": "staff@test.ch", "password": "password123"})
    assert client.get("/api/v1/manager/plugins/").status_code == 403
    assert client.get("/api/v1/manager/platform/backups/").status_code == 403
    assert client.get("/api/v1/system/tenants").status_code == 200

    # Not offered for roles either, and the seed takes the links away.
    keys = {
        p["key"]
        for p in client.get("/api/v1/system/global-permissions").get_json()["permissions"]
    }
    assert "plugins.manage" not in keys and "tenants.admins.write" in keys
    seed_global_rbac()
    linked = db.session.scalars(
        select(GlobalPermission.key)
        .join(GlobalRolePermission, GlobalRolePermission.permission_id == GlobalPermission.id)
        .where(GlobalRolePermission.role_id == role.id)
    ).all()
    assert "plugins.manage" not in linked and "backups.manage" not in linked


def test_the_old_superadmin_role_is_renamed(db, seeded_db):
    from hubra.api.global_rbac_seed import seed_global_rbac
    from hubra.core.models.global_role import GlobalRole

    db.session.add(GlobalRole(name="Superadmin", description="old", is_system=True))
    db.session.commit()
    seed_global_rbac()
    names = set(db.session.scalars(select(GlobalRole.name)).all())
    assert "Platform admin" in names and "Superadmin" not in names
