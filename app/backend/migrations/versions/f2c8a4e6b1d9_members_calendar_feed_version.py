"""A member can renew their calendar feed link

``members.calendar_feed_version`` is part of the signed feed token; raising
it makes every older link stop working. Added to the template table in
public and to every club schema.

Revision ID: f2c8a4e6b1d9
Revises: c5e2a8d4f1b7
Create Date: 2026-10-31 07:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f2c8a4e6b1d9"
down_revision = "c5e2a8d4f1b7"
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
        if "calendar_feed_version" not in have:
            op.add_column(
                "members",
                sa.Column(
                    "calendar_feed_version",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                ),
                schema=schema,
            )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        have = {c["name"] for c in inspector.get_columns("members", schema=schema)}
        if "calendar_feed_version" in have:
            op.drop_column("members", "calendar_feed_version", schema=schema)
