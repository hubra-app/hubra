"""Members choose what the club's directory shows of them

``members.directory_shared`` lists the contact data ("email", "phone",
"address", "birthday") a member shows other members. Empty until they
choose. Added to the template table in public and to every club schema.

Revision ID: e5a1c7f3b9d4
Revises: d7b3f9e1a5c2
Create Date: 2026-10-29 08:30:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "e5a1c7f3b9d4"
down_revision = "d7b3f9e1a5c2"
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
        if "directory_shared" not in have:
            op.add_column(
                "members",
                sa.Column(
                    "directory_shared",
                    sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
                    nullable=True,
                ),
                schema=schema,
            )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        have = {c["name"] for c in inspector.get_columns("members", schema=schema)}
        if "directory_shared" in have:
            op.drop_column("members", "directory_shared", schema=schema)
