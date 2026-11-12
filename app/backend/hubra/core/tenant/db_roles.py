"""One database role per club (docs/club-db-roles.md).

Every process connects as the app role, which can reach every club's
schema. Inside a club (a request, a job, ``in_club``) the connection now
also switches to that club's own role with ``SET ROLE``. The club role has
the rights it needs on its own schema and on the shared tables in public,
and none on other clubs' schemas or on the template copies of the club
tables in public. So a query that names another club's schema, or a club
table that is missing from the club's schema (and would fall through to the
template in public), fails with "permission denied" instead of reading or
writing someone else's rows.

What it guards against: bugs (a wrong search_path, a schema-qualified query,
a missing table). It is not a wall against code that means harm: the
session still logs in as the app role, so SQL that runs ``RESET ROLE``
gets the app role's rights back. Plugins are signed for that reason.

Roles are named ``<database>_club_<id>`` (cluster-wide names, so two Hubra
databases on one server never share one), all members of
``<database>_clubs``, which holds the rights on public.

The app role needs CREATEROLE (scripts/pg-init, scripts/pg-app-role-upgrade.sh)
or to be a superuser. Without it nothing changes: :func:`available` is
False, no role is made and no ``SET ROLE`` is sent. A club whose role does
not exist yet also runs as before; ``flask sync-tenant-schemas`` (the init
step, on every start) creates the missing ones.
"""

from __future__ import annotations

import logging
import re
import threading
import time

from sqlalchemy import text
from sqlalchemy.engine import Connection

_log = logging.getLogger(__name__)

# How long a process trusts its list of existing club roles.
_CACHE_SECONDS = 60
_lock = threading.Lock()
_cache: dict = {"at": 0.0, "roles": frozenset(), "prefix": None}

TABLE_RIGHTS = "SELECT, INSERT, UPDATE, DELETE, REFERENCES, TRIGGER"
SEQUENCE_RIGHTS = "USAGE, SELECT, UPDATE"


def _q(name: str) -> str:
    """A quoted identifier (role names are built from known parts only)."""
    return '"' + name.replace('"', '""') + '"'


def prefix_for(database: str) -> str:
    """The role name prefix for *database*: letters, digits, underscores."""
    clean = re.sub(r"[^a-z0-9_]", "_", database.lower()).strip("_") or "hubra"
    return clean[:40]


def _prefix(conn: Connection) -> str:
    if _cache["prefix"] is None:
        _cache["prefix"] = prefix_for(
            conn.exec_driver_sql("SELECT current_database()").scalar()
        )
    return _cache["prefix"]


def role_name(conn: Connection, tenant_id: int) -> str:
    return f"{_prefix(conn)}_club_{int(tenant_id)}"


def group_name(conn: Connection) -> str:
    return f"{_prefix(conn)}_clubs"


def available(conn: Connection) -> bool:
    """True when the app role may create the club roles."""
    if conn.dialect.name != "postgresql":
        return False
    return bool(
        conn.exec_driver_sql(
            "SELECT rolsuper OR rolcreaterole FROM pg_roles WHERE rolname = current_user"
        ).scalar()
    )


def _exists(conn: Connection, role: str) -> bool:
    return bool(
        conn.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role}
        ).scalar()
    )


def _schema_exists(conn: Connection, schema: str) -> bool:
    return bool(
        conn.execute(
            text("SELECT 1 FROM pg_namespace WHERE nspname = :s"), {"s": schema}
        ).scalar()
    )


def _create(conn: Connection, role: str) -> None:
    if not _exists(conn, role):
        conn.exec_driver_sql(f"CREATE ROLE {_q(role)} NOLOGIN INHERIT")
    # The app role must be a member to SET ROLE to it (PostgreSQL 16 gives
    # the creator only the ADMIN option).
    conn.exec_driver_sql(f"GRANT {_q(role)} TO CURRENT_USER")


def sync_public(conn: Connection, tenant_tables: list[str]) -> None:
    """The group role's rights on public: every shared table, none of the
    club tables' templates. Run after every migration and plugin change."""
    group = group_name(conn)
    _create(conn, group)
    conn.exec_driver_sql(f"GRANT USAGE ON SCHEMA public TO {_q(group)}")
    db = conn.exec_driver_sql("SELECT current_database()").scalar()
    conn.exec_driver_sql(f"GRANT CONNECT, TEMP ON DATABASE {_q(db)} TO {_q(group)}")
    templates = set(tenant_tables)
    tables = conn.exec_driver_sql(
        "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm')"
    ).scalars()
    for table in tables:
        if table in templates:
            conn.exec_driver_sql(f"REVOKE ALL ON public.{_q(table)} FROM {_q(group)}")
        else:
            conn.exec_driver_sql(
                f"GRANT {TABLE_RIGHTS} ON public.{_q(table)} TO {_q(group)}"
            )
    conn.exec_driver_sql(
        f"GRANT {SEQUENCE_RIGHTS} ON ALL SEQUENCES IN SCHEMA public TO {_q(group)}"
    )
    # Shared tables and sequences that migrations add later; templates among
    # them lose it again on the next sync (the init step, plugin installs).
    conn.exec_driver_sql(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT {TABLE_RIGHTS} ON TABLES TO {_q(group)}"
    )
    conn.exec_driver_sql(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT {SEQUENCE_RIGHTS} ON SEQUENCES TO {_q(group)}"
    )


def ensure_club(conn: Connection, tenant_id: int) -> str | None:
    """Create the club's role and give it its schema. Returns the role, or
    None when roles can't be made here or the schema doesn't exist."""
    if not available(conn):
        return None
    schema = f"tenant_{int(tenant_id)}"
    if not _schema_exists(conn, schema):
        return None
    role = role_name(conn, tenant_id)
    _create(conn, role)
    conn.exec_driver_sql(f"GRANT {_q(group_name(conn))} TO {_q(role)}")
    conn.exec_driver_sql(f"GRANT USAGE, CREATE ON SCHEMA {schema} TO {_q(role)}")
    conn.exec_driver_sql(f"GRANT ALL ON ALL TABLES IN SCHEMA {schema} TO {_q(role)}")
    conn.exec_driver_sql(f"GRANT ALL ON ALL SEQUENCES IN SCHEMA {schema} TO {_q(role)}")
    # Tables a later migration adds to the club's schema (as the app role).
    conn.exec_driver_sql(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT ALL ON TABLES TO {_q(role)}"
    )
    conn.exec_driver_sql(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT ALL ON SEQUENCES TO {_q(role)}"
    )
    forget()
    return role


def drop_club(conn: Connection, tenant_id: int) -> None:
    """Remove the club's role (after its schema is gone)."""
    if conn.dialect.name != "postgresql":
        return
    role = role_name(conn, tenant_id)
    if not _exists(conn, role):
        return
    conn.exec_driver_sql(f"DROP OWNED BY {_q(role)}")
    conn.exec_driver_sql(f"DROP ROLE {_q(role)}")
    forget()


def sync_all(conn: Connection, tenant_tables: list[str]) -> list[str]:
    """Public rights plus a role for every club schema. Returns the roles."""
    if not available(conn):
        return []
    sync_public(conn, tenant_tables)
    ids = conn.exec_driver_sql(
        "SELECT substring(nspname from 8)::int FROM pg_namespace "
        "WHERE nspname ~ '^tenant_[0-9]+$' ORDER BY 1"
    ).scalars()
    return [r for r in (ensure_club(conn, i) for i in ids) if r]


# ── At run time ──────────────────────────────────────────────────────────────


def forget() -> None:
    """Re-read the existing roles on the next lookup."""
    with _lock:
        _cache["at"] = 0.0


def active_role(conn: Connection, tenant_id: int) -> str | None:
    """The club's role when it exists, else None (the club runs as before)."""
    if conn.dialect.name != "postgresql":
        return None
    now = time.monotonic()
    with _lock:
        fresh = now - _cache["at"] < _CACHE_SECONDS
    if not fresh:
        pattern = f"{_prefix(conn)}\\_club\\_%"
        roles = frozenset(
            conn.execute(
                text("SELECT rolname FROM pg_roles WHERE rolname LIKE :p"),
                {"p": pattern},
            ).scalars()
        )
        with _lock:
            _cache.update(at=now, roles=roles)
    role = role_name(conn, tenant_id)
    return role if role in _cache["roles"] else None
