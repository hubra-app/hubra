"""Polls that close once everyone has voted (circular resolutions)

``polls.auto_close``: a poll for named groups or functions closes by itself
when the last of them has voted (Umlaufbeschluss). Added to the template
table in public and to every club schema.

Revision ID: b4e8f2a6d9c3
Revises: b4e8f2a6c1d9
Create Date: 2026-11-04 11:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b4e8f2a6d9c3"
down_revision = "b4e8f2a6c1d9"
branch_labels = None
depends_on = None


def _schemas():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return [None]
    rows = bind.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'polls' ORDER BY table_schema"
        )
    ).scalars()
    return list(rows)


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        have = {c["name"] for c in inspector.get_columns("polls", schema=schema)}
        if "auto_close" not in have:
            op.add_column(
                "polls",
                sa.Column(
                    "auto_close",
                    sa.Boolean(),
                    server_default=sa.false(),
                    nullable=False,
                ),
                schema=schema,
            )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        have = {c["name"] for c in inspector.get_columns("polls", schema=schema)}
        if "auto_close" in have:
            op.drop_column("polls", "auto_close", schema=schema)
