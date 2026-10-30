"""Roles held for one group only

``member_role_scopes`` gives a member a role for one group ("Event-Organisation
for Jugend"); its permissions count on that group's routes only. Added to the
template table in public and to every club schema.

Revision ID: c4e8a2f6b1d3
Revises: b3d7f1a9c2e4
Create Date: 2026-10-30 19:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c4e8a2f6b1d3"
down_revision = "b3d7f1a9c2e4"
branch_labels = None
depends_on = None

TABLE = "member_role_scopes"


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
        if inspector.has_table(TABLE, schema=schema):
            continue
        ref = f"{schema}." if schema else ""
        op.create_table(
            TABLE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "member_id",
                sa.Integer(),
                sa.ForeignKey(f"{ref}members.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "role_id",
                sa.Integer(),
                sa.ForeignKey(f"{ref}roles.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "group_id",
                sa.Integer(),
                sa.ForeignKey(f"{ref}groups.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.UniqueConstraint("member_id", "role_id", "group_id"),
            schema=schema,
        )
        for column in ("member_id", "role_id", "group_id"):
            op.create_index(
                f"ix_{TABLE}_{column}", TABLE, [column], schema=schema
            )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        if inspector.has_table(TABLE, schema=schema):
            op.drop_table(TABLE, schema=schema)
