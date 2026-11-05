"""Own dashboards

``dashboards``: a member's dashboard (name, widgets, shared with the club
or not). Added to the template tables in public and to every club schema.

Revision ID: f2a6c8e4b1d7
Revises: c3e7a1f5b9d2
Create Date: 2026-11-05 21:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "f2a6c8e4b1d7"
down_revision = "c3e7a1f5b9d2"
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
        ref = f"{schema}." if schema else ""
        if inspector.has_table("dashboards", schema=schema):
            continue
        op.create_table(
            "dashboards",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column(
                "owner_id",
                sa.Integer(),
                sa.ForeignKey(f"{ref}members.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("shared", sa.Boolean(), nullable=False),
            sa.Column("widgets", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            schema=schema,
        )
        op.create_index(
            "ix_dashboards_owner_id", "dashboards", ["owner_id"], schema=schema
        )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        if inspector.has_table("dashboards", schema=schema):
            op.drop_table("dashboards", schema=schema)
