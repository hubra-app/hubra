"""Posts in several languages

``posts.language`` is the language a post was written in and
``posts.translations`` holds its other languages. Added to the template
tables in public and to every club schema.

Revision ID: b7d1f3a9c5e2
Revises: d2b8f4a6c0e3
Create Date: 2026-11-05 23:30:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b7d1f3a9c5e2"
down_revision = "d2b8f4a6c0e3"
branch_labels = None
depends_on = None


def _schemas():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return [None]
    rows = bind.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'posts' ORDER BY table_schema"
        )
    ).scalars()
    return list(rows)


def _json():
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.JSONB()
    return sa.JSON()


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        have = {c["name"] for c in inspector.get_columns("posts", schema=schema)}
        if "language" not in have:
            op.add_column(
                "posts", sa.Column("language", sa.String(5), nullable=True), schema=schema
            )
        if "translations" not in have:
            op.add_column(
                "posts", sa.Column("translations", _json(), nullable=True), schema=schema
            )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        have = {c["name"] for c in inspector.get_columns("posts", schema=schema)}
        for name in ("translations", "language"):
            if name in have:
                op.drop_column("posts", name, schema=schema)
