"""Groups drop the hand-typed tools count

``groups.tools`` was a number typed in by hand and shown as a badge on the
group card, linked to nothing. Dropped from the template table in public
and from every club schema.

Revision ID: f2c8a4d6b1e3
Revises: c5e2a8d4f1b7
Create Date: 2026-10-31 06:15:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f2c8a4d6b1e3"
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
            "WHERE table_name = 'groups' ORDER BY table_schema"
        )
    ).scalars()
    return list(rows)


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        have = {c["name"] for c in inspector.get_columns("groups", schema=schema)}
        if "tools" in have:
            op.drop_column("groups", "tools", schema=schema)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        have = {c["name"] for c in inspector.get_columns("groups", schema=schema)}
        if "tools" not in have:
            op.add_column(
                "groups",
                sa.Column("tools", sa.Integer(), nullable=False, server_default="0"),
                schema=schema,
            )
