"""Helpers for plugin migrations.

Plugin migrations run once in the public schema and once per club, with
``search_path`` set to the club's schema first.  SQLAlchemy's inspector
treats any table visible on the search path as present, so a table in
public would hide a club's missing one.  These look in the current schema
only::

    from hubra.core.plugins.ops import has_table

    def upgrade():
        if not has_table("keys"):
            op.create_table("keys", ...)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


def current_schema() -> str | None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return None
    return bind.execute(sa.text("SELECT current_schema()")).scalar()


def has_table(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table, schema=current_schema())


def columns(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    schema = current_schema()
    if not insp.has_table(table, schema=schema):
        return set()
    return {c["name"] for c in insp.get_columns(table, schema=schema)}
