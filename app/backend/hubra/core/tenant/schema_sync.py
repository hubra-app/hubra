"""Bring club schemas in line with the template tables in public.

A club schema is a clone of the module tables in public, made when the club
was created (``schema_manager.create_tenant_schema``).  After that, a core
migration only reaches the club schemas if it loops over them itself.  Two
that did not (``0ac79fcc9933`` recurring transactions, ``ee771f92971b``
invoice periods) left every club created before them without
``transactions.recurring_id``, ``invoices.period_start``/``period_end`` and
the ``recurring_transactions`` table, so the finance pages failed with
``UndefinedColumn`` and recurring transactions fell through to the table in
public (the search path is ``tenant_<id>, public``).

:func:`catch_up` adds what public has and a club schema lacks: missing
tables (cloned like a new club's, with their own id sequences) and missing
columns (with their type, default and the indexes on them).  It never drops
or changes anything, so running it again does nothing.  The init step runs
it on every start (``flask sync-tenant-schemas``), so a migration that
forgets the club schemas no longer breaks them.

Foreign keys are not copied, the same as for a new club's clone.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.engine import Connection

_log = logging.getLogger(__name__)


@dataclass
class CatchUp:
    """What :func:`catch_up` added to one schema."""

    schema: str
    tables: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)  # "table.column"
    indexes: list[str] = field(default_factory=list)
    # Tables that were missing here but have rows in public: rows a club
    # wrote while its own table was missing.  Reported, never moved.
    rows_in_public: dict[str, int] = field(default_factory=dict)

    @property
    def changed(self) -> bool:
        return bool(self.tables or self.columns or self.indexes)


def club_schemas(conn: Connection) -> list[str]:
    return list(
        conn.execute(
            text(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name LIKE 'tenant\\_%' ORDER BY schema_name"
            )
        ).scalars()
    )


def _exists(conn: Connection, schema: str, table: str) -> bool:
    return (
        conn.execute(
            text("SELECT to_regclass(:name)"), {"name": f"{schema}.{table}"}
        ).scalar()
        is not None
    )


def _columns(conn: Connection, schema: str, table: str) -> list[tuple]:
    """``(name, type, not_null, default)`` per column, in table order."""
    return conn.execute(
        text(
            "SELECT a.attname, format_type(a.atttypid, a.atttypmod), "
            "a.attnotnull, pg_get_expr(d.adbin, d.adrelid) "
            "FROM pg_attribute a "
            "LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum "
            "WHERE a.attrelid = to_regclass(:name) AND a.attnum > 0 "
            "AND NOT a.attisdropped ORDER BY a.attnum"
        ),
        {"name": f"{schema}.{table}"},
    ).all()


def _indexes_on(conn: Connection, table: str, columns: set[str]) -> list[tuple]:
    """``(name, definition)`` of public's indexes on *table* that use only
    *columns* (the ones just added to the club's table)."""
    rows = conn.execute(
        text(
            "SELECT i.relname, pg_get_indexdef(x.indexrelid), "
            "array_agg(a.attname::text) "
            "FROM pg_index x "
            "JOIN pg_class i ON i.oid = x.indexrelid "
            "JOIN pg_attribute a ON a.attrelid = x.indrelid "
            "  AND a.attnum = ANY(x.indkey) "
            "WHERE x.indrelid = to_regclass(:name) AND NOT x.indisprimary "
            "GROUP BY i.relname, x.indexrelid"
        ),
        {"name": f"public.{table}"},
    ).all()
    return [(name, sql) for name, sql, cols in rows if cols and set(cols) <= columns]


def _own_sequences(conn: Connection, schema: str, table: str) -> None:
    """The id sequences of a freshly cloned table, as in
    ``schema_manager._own_sequences``: its own, not public's."""
    cols = conn.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table "
            "AND column_default LIKE 'nextval(%'"
        ),
        {"schema": schema, "table": table},
    ).scalars()
    for column in list(cols):
        seq = f"{schema}.{table}_{column}_seq"
        conn.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {seq}"))
        conn.execute(
            text(
                f"SELECT setval('{seq}', "
                f"COALESCE((SELECT MAX({column}) FROM {schema}.{table}), 0) + 1, false)"
            )
        )
        conn.execute(
            text(
                f"ALTER TABLE {schema}.{table} ALTER COLUMN {column} "
                f"SET DEFAULT nextval('{seq}'::regclass)"
            )
        )
        conn.execute(text(f"ALTER SEQUENCE {seq} OWNED BY {schema}.{table}.{column}"))


def catch_up(conn: Connection, schema: str, tables: list[str]) -> CatchUp:
    """Add *tables* and their columns that public has and *schema* lacks."""
    if not schema.startswith("tenant_") or not schema[7:].isdigit():
        raise ValueError(f"not a club schema: {schema!r}")
    done = CatchUp(schema)
    for table in tables:
        if not _exists(conn, "public", table):
            continue  # a module or plugin table that public does not have
        if not _exists(conn, schema, table):
            conn.execute(
                text(
                    f"CREATE TABLE {schema}.{table} "
                    f"(LIKE public.{table} INCLUDING ALL EXCLUDING STATISTICS)"
                )
            )
            _own_sequences(conn, schema, table)
            done.tables.append(table)
            rows = conn.execute(text(f"SELECT count(*) FROM public.{table}")).scalar()
            if rows:
                done.rows_in_public[table] = int(rows)
            continue

        have = {c[0] for c in _columns(conn, schema, table)}
        added: set[str] = set()
        for name, type_, not_null, default in _columns(conn, "public", table):
            if name in have:
                continue
            sql = f'ALTER TABLE {schema}.{table} ADD COLUMN "{name}" {type_}'
            if default and not default.startswith("nextval("):
                sql += f" DEFAULT {default}"
                if not_null:
                    sql += " NOT NULL"
            conn.execute(text(sql))
            added.add(name)
            done.columns.append(f"{table}.{name}")
        if not added:
            continue
        for index, definition in _indexes_on(conn, table, added):
            # "CREATE [UNIQUE] INDEX name ON public.t USING …" → this schema.
            head, sep, rest = definition.partition(f" ON public.{table} ")
            if not sep:
                continue
            head = head.replace(" INDEX ", " INDEX IF NOT EXISTS ", 1)
            conn.execute(text(f"{head} ON {schema}.{table} {rest}"))
            done.indexes.append(index)
    return done


def catch_up_all(conn: Connection, tables: list[str]) -> list[CatchUp]:
    """:func:`catch_up` for every club schema; the ones that changed."""
    if conn.dialect.name != "postgresql":
        return []
    out = []
    for schema in club_schemas(conn):
        result = catch_up(conn, schema, tables)
        if result.changed:
            _log.warning(
                "Club schema %s caught up with public: tables %s, columns %s",
                schema,
                result.tables or "-",
                result.columns or "-",
            )
            out.append(result)
    return out
