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
    column types, defaults, constraints, and indexes. The core tables use
    SERIAL, so the copied defaults still draw from public's sequences;
    ``_own_sequences`` gives the club its own.

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

    _own_sequences(schema_name)
    _create_tenant_indexes(schema_name)
    _init_alembic_version(schema_name)
    _init_plugin_versions(schema_name)

    db.session.commit()
    _log.info("Tenant schema %s created successfully", schema_name)


def drop_tenant_schema(tenant_id: int) -> None:
    """Drop the tenant schema and all its contents (CASCADE)."""
    schema_name = f"tenant_{tenant_id}"
    _log.warning("Dropping tenant schema: %s", schema_name)
    db.session.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
    db.session.commit()


# ── Internal helpers ───────────────────────────────────────────────────────


def _own_sequences(schema_name: str) -> None:
    """Give every id column of the club its own sequence.

    ``LIKE ... INCLUDING ALL`` copies a SERIAL column's default, which still
    calls ``nextval`` on the sequence in public, so all clubs shared one
    counter per table: numbers jumped with other clubs' activity, and a
    club's data could not move to another instance without collisions.
    Each column gets ``<schema>.<table>_<column>_seq``, started after the
    highest id already there.
    """
    columns = db.session.execute(
        text(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = :schema AND column_default LIKE :pattern"
        ),
        {"schema": schema_name, "pattern": "nextval(%"},
    ).all()
    for table, column in columns:
        seq = f"{schema_name}.{table}_{column}_seq"
        db.session.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {seq}"))
        db.session.execute(
            text(
                f"SELECT setval('{seq}', "
                f"COALESCE((SELECT MAX({column}) FROM {schema_name}.{table}), 0) + 1, "
                "false)"
            )
        )
        db.session.execute(
            text(
                f"ALTER TABLE {schema_name}.{table} ALTER COLUMN {column} "
                f"SET DEFAULT nextval('{seq}'::regclass)"
            )
        )
        db.session.execute(
            text(f"ALTER SEQUENCE {seq} OWNED BY {schema_name}.{table}.{column}")
        )


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


def _init_plugin_versions(schema_name: str) -> None:
    """Copy each loaded plugin's version table from public.

    The plugin's tables were cloned above, so the club starts at the same
    plugin revisions as public.
    """
    from hubra.core.plugins import current

    for spec in current().loaded():
        if spec.migrations_dir is None:
            continue
        table = spec.version_table
        exists = db.session.execute(
            text("SELECT to_regclass(:name)"), {"name": f"public.{table}"}
        ).scalar()
        if exists is None:
            continue
        db.session.execute(
            text(
                f"CREATE TABLE IF NOT EXISTS {schema_name}.{table} "
                f"(LIKE public.{table} INCLUDING ALL)"
            )
        )
        db.session.execute(
            text(
                f"INSERT INTO {schema_name}.{table} (version_num) "
                f"SELECT version_num FROM public.{table} ON CONFLICT DO NOTHING"
            )
        )
