"""Schema lifecycle — create, clone, drop tenant schemas."""

from __future__ import annotations

import logging

from sqlalchemy import text

from hubra.core.extensions import db

_log = logging.getLogger(__name__)


def tables_to_clone() -> list[str]:
    """Tenant-schema tables, as declared by the module manifests."""
    from hubra.core.modules import registry

    registry.load()
    return registry.tenant_tables()


def create_tenant_schema(tenant_id: int) -> None:
    """Create ``tenant_{id}`` schema and clone all domain tables from public.

    Uses ``CREATE TABLE ... (LIKE public.<tbl> INCLUDING ALL)`` to copy
    column types, defaults, constraints, and indexes.  Sequences for identity
    columns are cloned automatically by ``INCLUDING DEFAULTS`` when the
    existing tables use ``Identity`` (not ``Serial``).

    Does NOT copy foreign key constraints pointing to other tables — those
    must be re-created in the tenant schema context after all tables exist.
    """
    schema_name = f"tenant_{tenant_id}"

    _log.info("Creating tenant schema: %s", schema_name)
    db.session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))

    for table in tables_to_clone():
        sql = text(
            f"CREATE TABLE IF NOT EXISTS {schema_name}.{table} "
            f"(LIKE public.{table} INCLUDING ALL EXCLUDING STATISTICS)"
        )
        try:
            db.session.execute(sql)
            _log.debug("  Cloned table %s", table)
        except Exception:
            _log.exception("Failed to clone table %s into %s", table, schema_name)
            raise

    _create_tenant_indexes(schema_name)
    _init_alembic_version(schema_name)

    db.session.commit()
    _log.info("Tenant schema %s created successfully", schema_name)


def drop_tenant_schema(tenant_id: int) -> None:
    """Drop the tenant schema and all its contents (CASCADE)."""
    schema_name = f"tenant_{tenant_id}"
    _log.warning("Dropping tenant schema: %s", schema_name)
    db.session.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
    db.session.commit()


# ── Internal helpers ───────────────────────────────────────────────────────


def _create_tenant_indexes(schema_name: str) -> None:
    """Recreate cross-table foreign key constraints in the tenant schema.

    ``CREATE TABLE ... LIKE ...`` does not copy FKs whose referenced table
    is in another schema.  We re-create the known FKs here after all tables
    have been cloned.
    """
    # FKs that point between domain tables (not to public.tenants etc.)
    _fk_statements = [
        f"ALTER TABLE {schema_name}.audit_entries "
        f"ADD CONSTRAINT audit_entries_actor_id_fkey "
        f"FOREIGN KEY (actor_id) REFERENCES {schema_name}.members(id);",
        f"ALTER TABLE {schema_name}.sessions "
        f"ADD CONSTRAINT sessions_device_id_fkey "
        f"FOREIGN KEY (device_id) REFERENCES {schema_name}.devices(id);",
        f"ALTER TABLE {schema_name}.devices "
        f"ADD CONSTRAINT devices_member_id_fkey "
        f"FOREIGN KEY (member_id) REFERENCES {schema_name}.members(id);",
    ]

    for stmt in _fk_statements:
        try:
            db.session.execute(text(stmt))
        except Exception:
            _log.warning("FK statement failed (may already exist): %s", stmt[:80])


def _init_alembic_version(schema_name: str) -> None:
    """Create the alembic_version table in the tenant schema.

    This allows per-tenant migration tracking by Flask-Migrate.
    The initial version is copied from public so the tenant starts
    at the same migration state.
    """
    # Create the version table
    db.session.execute(
        text(
            f"CREATE TABLE IF NOT EXISTS {schema_name}.alembic_version ("
            "version_num VARCHAR(32) NOT NULL, "
            "PRIMARY KEY (version_num)"
            ")"
        )
    )

    # Copy the current public migration version
    public_version = db.session.execute(
        text(
            "SELECT version_num FROM public.alembic_version ORDER BY version_num DESC LIMIT 1"
        )
    ).scalar()

    if public_version:
        db.session.execute(
            text(
                f"INSERT INTO {schema_name}.alembic_version (version_num) "
                f"VALUES (:ver) ON CONFLICT DO NOTHING"
            ),
            {"ver": public_version},
        )
        _log.debug(
            "  Initialised alembic_version at %s for %s",
            public_version,
            schema_name,
        )
