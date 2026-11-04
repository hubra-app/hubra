"""support_cases.roadmap_item + roadmap_votes: one public roadmap

An idea can be linked to an item of the planned roadmap (ROADMAP.yaml id),
and people can vote for planned items directly.

Public-schema only, so the revision is safe to run again per club
(flask migrate-tenants).

Revision ID: d8a3f1c6b2e7
Revises: c3d7a1e5f9b2
Create Date: 2026-11-04 10:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d8a3f1c6b2e7"
down_revision = "c3d7a1e5f9b2"
branch_labels = None
depends_on = None


def _public_schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def upgrade():
    schema = _public_schema()
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("support_cases", schema=schema):
        cols = {c["name"] for c in inspector.get_columns("support_cases", schema=schema)}
        if "roadmap_item" not in cols:
            op.add_column(
                "support_cases",
                sa.Column("roadmap_item", sa.String(64), nullable=True),
                schema=schema,
            )
            op.create_index(
                "ix_support_cases_roadmap_item",
                "support_cases",
                ["roadmap_item"],
                schema=schema,
            )
    if not inspector.has_table("roadmap_votes", schema=schema):
        op.create_table(
            "roadmap_votes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("item", sa.String(64), nullable=False),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("item", "user_id", name="uq_roadmap_vote"),
            schema=schema,
        )
        op.create_index(
            "ix_roadmap_votes_item", "roadmap_votes", ["item"], schema=schema
        )


def downgrade():
    schema = _public_schema()
    op.drop_table("roadmap_votes", schema=schema)
    op.drop_index("ix_support_cases_roadmap_item", "support_cases", schema=schema)
    op.drop_column("support_cases", "roadmap_item", schema=schema)
