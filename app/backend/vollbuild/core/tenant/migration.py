"""Migration helpers — apply Alembic migrations to tenant schemas."""

from __future__ import annotations

import logging

from sqlalchemy import select, text

from vollbuild.extensions import db
from vollbuild.core.models.tenant import Tenant

from .context import set_search_path

_log = logging.getLogger(__name__)


def apply_migrations_to_tenant(tenant_id: int) -> None:
    """Run all pending Alembic migrations against a single tenant schema.

    Sets the search_path to ``tenant_{id}`` so that ``flask db upgrade``
    operates on the tenant schema rather than public.
    """
    schema = f"tenant_{tenant_id}"
    _log.info("Applying migrations to tenant schema: %s", schema)

    set_search_path(tenant_id)
    db.session.commit()  # ensure search_path is visible to Alembic connection

    from flask_migrate import upgrade as _upgrade

    _upgrade()

    # Reset search_path back to public
    db.session.execute(text("SET search_path TO public"))
    db.session.commit()
    _log.info("Migrations applied to %s", schema)


def apply_migrations_to_all_tenants() -> int:
    """Iterate all active tenants and apply pending migrations.

    Returns the number of tenants processed.
    """
    tenants = db.session.scalars(select(Tenant).where(Tenant.status == "active")).all()

    count = 0
    for tenant in tenants:
        try:
            apply_migrations_to_tenant(tenant.id)
            count += 1
        except Exception:
            _log.exception(
                "Migration failed for tenant %s (id=%d)", tenant.slug, tenant.id
            )
            raise

    return count


def ensure_tenant_has_alembic(tenant_id: int) -> None:
    """Ensure the tenant schema has an alembic_version table.

    Called during provisioning to guarantee migration tracking is in place.
    """
    schema = f"tenant_{tenant_id}"
    db.session.execute(
        text(
            f"CREATE TABLE IF NOT EXISTS {schema}.alembic_version ("
            "version_num VARCHAR(32) NOT NULL, "
            "PRIMARY KEY (version_num)"
            ")"
        )
    )
    db.session.commit()
