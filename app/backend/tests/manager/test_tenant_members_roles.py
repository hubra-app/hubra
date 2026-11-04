"""GET /system/tenants/<id>/members lists each member's roles."""

from unittest.mock import patch

from hubra.core.models.tenant import Tenant
from hubra.core.models.user import User


def test_member_list_includes_roles(client, db):
    tenant = Tenant(name="Roles Club", slug="roles-club", plan="starter")
    db.session.add(tenant)
    db.session.flush()
    with (
        patch("hubra.core.tenant.context.set_search_path"),
        patch("hubra.core.tenant.context.reset_search_path"),
    ):
        from hubra.core.tenant.service import _seed_tenant

        _seed_tenant(tenant.id, "owner@roles.test", "VeryStrongPass123!")
    db.session.commit()

    admin = User(
        email="platform@roles.test",
        first_name="Platform",
        last_name="Admin",
        is_superadmin=True,
    )
    admin.set_password("VeryStrongPass123!")
    db.session.add(admin)
    db.session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "platform@roles.test", "password": "VeryStrongPass123!"},
    )

    # The roles live in the club's schema: they must be read while the
    # schema is on the search path, not after it was reset.
    with (
        patch("hubra.core.tenant.context.set_search_path"),
        patch("hubra.core.tenant.context.reset_search_path"),
    ):
        resp = client.get(f"/api/v1/system/tenants/{tenant.id}/members")
    assert resp.status_code == 200
    owner = next(
        m for m in resp.get_json()["members"] if m["email"] == "owner@roles.test"
    )
    assert owner["roles"] == ["Owner"]
