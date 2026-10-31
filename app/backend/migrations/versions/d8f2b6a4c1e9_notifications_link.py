"""A notification links to what it is about

``notifications.link`` is the club app path a click opens, e.g.
"/app/operations/posts/3". Empty for older notifications. Added to the
template table in public and to every club schema.

Revision ID: d8f2b6a4c1e9
Revises: c5e2a8d4f1b7
Create Date: 2026-10-30 22:45:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d8f2b6a4c1e9"
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
            "WHERE table_name = 'notifications' ORDER BY table_schema"
        )
    ).scalars()
    return list(rows)


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        have = {c["name"] for c in inspector.get_columns("notifications", schema=schema)}
        if "link" not in have:
            op.add_column(
                "notifications",
                sa.Column("link", sa.String(255), nullable=True),
                schema=schema,
            )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        have = {c["name"] for c in inspector.get_columns("notifications", schema=schema)}
        if "link" in have:
            op.drop_column("notifications", "link", schema=schema)
