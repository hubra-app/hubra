"""Members can ask to leave a club

``members.leave_requested_at`` is set while a member's request to leave waits
for a club admin (clubs that switch on "leaving needs approval").  The column
is added to the template table in public and to every club schema.

Revision ID: e8f3b1d5c7a2
Revises: d7e2a9c4b6f1
Create Date: 2026-10-28 17:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e8f3b1d5c7a2"
down_revision = "d7e2a9c4b6f1"
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
        if "leave_requested_at" not in have:
            op.add_column(
                "members",
                sa.Column(
                    "leave_requested_at", sa.DateTime(timezone=True), nullable=True
                ),
                schema=schema,
            )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        have = {c["name"] for c in inspector.get_columns("members", schema=schema)}
        if "leave_requested_at" in have:
            op.drop_column("members", "leave_requested_at", schema=schema)
