"""A club provisioned on an empty permission catalog still gets working roles."""

from unittest.mock import patch

from sqlalchemy import func, select

from hubra.core.models.role import Permission, Role, RolePermission
from hubra.core.models.tenant import Tenant


def test_seed_tenant_fills_an_empty_catalog(db):
    assert db.session.scalar(select(func.count(Permission.id))) == 0

    tenant = Tenant(name="First Club", slug="first-club", plan="starter")
    db.session.add(tenant)
    db.session.flush()
    with (
        patch("hubra.core.tenant.context.set_search_path"),
        patch("hubra.core.tenant.context.reset_search_path"),
    ):
        from hubra.core.tenant.service import _seed_tenant

        _seed_tenant(tenant.id, None, None)
    db.session.commit()

    # The catalog was synced from the routes ...
    assert db.session.scalar(select(func.count(Permission.id))) > 100
    # ... so the Member role grants something instead of nothing.
    member = db.session.scalar(select(Role).where(Role.name == "Member"))
    granted = db.session.scalar(
        select(func.count(RolePermission.role_id)).where(
            RolePermission.role_id == member.id
        )
    )
    assert granted > 0
