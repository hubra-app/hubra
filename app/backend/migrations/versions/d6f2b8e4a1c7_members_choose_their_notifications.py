"""Members choose which notifications they get

``members.notify_prefs`` holds the topics and channels (bell, push) a member
turned off, e.g. {"posts": {"push": false}}. Empty means everything on.
Added to the template table in public and to every club schema.

Revision ID: d6f2b8e4a1c7
Revises: c8e2a4f6d1b9
Create Date: 2026-11-01 17:20:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "d6f2b8e4a1c7"
down_revision = "c8e2a4f6d1b9"
branch_labels = None
depends_on = None


def _schemas():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return [None]
    rows = bind.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'members' ORDER BY table_schema"
        )
    ).scalars()
    return list(rows)


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        have = {c["name"] for c in inspector.get_columns("members", schema=schema)}
        if "notify_prefs" not in have:
            op.add_column(
                "members",
                sa.Column(
                    "notify_prefs",
                    sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
                    nullable=True,
                ),
                schema=schema,
            )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        have = {c["name"] for c in inspector.get_columns("members", schema=schema)}
        if "notify_prefs" in have:
            op.drop_column("members", "notify_prefs", schema=schema)
