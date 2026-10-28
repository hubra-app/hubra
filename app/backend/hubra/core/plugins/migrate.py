"""Running a plugin's migrations in the public schema and in every club.

Each plugin's revisions live in its own ``migrations/`` folder and are
tracked in its own version table, so installing, updating or removing a
plugin never touches Hubra's migration chain (``flask db``).

Everything runs on the request's database connection: on PostgreSQL the
migrations of every schema and the ``installed_plugins`` row commit
together, or not at all.  A transaction-level advisory lock keeps two pods
from migrating at the same time.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select, text

from hubra.core.extensions import db

from .spec import Spec

_log = logging.getLogger(__name__)

ENV_DIR = Path(__file__).parent / "alembic"
LOCK_KEY = 0x48554252  # "HUBR"


def _config(spec: Spec, connection, schema: str | None) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(ENV_DIR))
    cfg.set_main_option("version_locations", str(spec.migrations_dir))
    cfg.set_main_option("path_separator", "os")
    cfg.attributes["connection"] = connection
    cfg.attributes["version_table"] = spec.version_table
    cfg.attributes["schema"] = schema
    cfg.attributes["tables"] = _tables(spec)
    return cfg


def _tables(spec: Spec) -> list[str]:
    tables: list[str] = []
    for m in spec.modules:
        tables.extend(m.tables)
    tables.extend(str(t) for t in spec.manifest.get("tables") or [])
    return tables


def _schemas() -> list[str | None]:
    """None (the public schema), then every active club's schema."""
    from hubra.core.models.tenant import Tenant

    if db.session.get_bind().dialect.name == "sqlite":
        return [None]
    ids = db.session.scalars(select(Tenant.id).where(Tenant.status == "active")).all()
    return [None, *(f"tenant_{i}" for i in ids)]


def _run(spec: Spec, fn, down: bool = False) -> list[str | None]:
    if spec.migrations_dir is None:
        return []
    conn = db.session.connection()
    postgres = conn.dialect.name == "postgresql"
    if postgres:
        conn.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": LOCK_KEY})
    done = []
    schemas = _schemas()
    if down:
        # Clubs first, and without public on the path: a club's drop must
        # never reach the public table of the same name.
        schemas = [*schemas[1:], schemas[0]]
    try:
        for schema in schemas:
            if postgres:
                if schema and down:
                    path = f'"{schema}"'
                else:
                    path = f'"{schema}", public' if schema else "public"
                conn.execute(text(f"SET search_path TO {path}"))
            fn(_config(spec, conn, schema))
            done.append(schema)
    finally:
        if postgres:
            conn.execute(text("SET search_path TO public"))
    return done


def upgrade_everywhere(spec: Spec) -> list[str | None]:
    """Bring the plugin's tables up to date in public and in every club."""
    done = _run(spec, lambda cfg: command.upgrade(cfg, "heads"))
    _log.info("Plugin %s migrated in %d schema(s)", spec.id, len(done))
    return done


def downgrade_everywhere(spec: Spec) -> list[str | None]:
    """Run the plugin's migrations down to nothing (deletes its data)."""

    def down(cfg):
        command.downgrade(cfg, "base")
        schema = cfg.attributes["schema"]
        name = f'"{schema}".{spec.version_table}' if schema else spec.version_table
        cfg.attributes["connection"].execute(text(f"DROP TABLE IF EXISTS {name}"))

    done = _run(spec, down, down=True)
    _log.info("Plugin %s removed from %d schema(s)", spec.id, len(done))
    return done


def upgrade_schema(spec: Spec, schema: str) -> None:
    """Migrate one club's schema (a club created after the install)."""
    conn = db.session.connection()
    if spec.migrations_dir is None:
        return
    conn.execute(text(f'SET search_path TO "{schema}", public'))
    try:
        command.upgrade(_config(spec, conn, schema), "heads")
    finally:
        conn.execute(text("SET search_path TO public"))


def revision(spec: Spec, message: str, autogenerate: bool) -> None:
    """``flask plugins revision``: a new migration in the plugin's folder."""
    if spec.migrations_dir is None:
        raise ValueError(f"{spec.id}: plugin.yaml has no migrations folder")
    conn = db.session.connection()
    cfg = _config(spec, conn, None)
    command.revision(
        cfg,
        message=message,
        autogenerate=autogenerate,
        version_path=str(spec.migrations_dir),
    )
    db.session.rollback()
