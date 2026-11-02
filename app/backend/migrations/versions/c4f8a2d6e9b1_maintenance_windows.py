"""maintenance_windows: planned maintenance for every club or some clubs

Public-schema only, so the revision is safe to run again per club
(flask migrate-tenants): the table goes to public, once.

Revision ID: c4f8a2d6e9b1
Revises: e7b3d9f1a2c4
Create Date: 2026-11-02 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "c4f8a2d6e9b1"
down_revision = "e7b3d9f1a2c4"
branch_labels = None
depends_on = None


def _public_schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def upgrade():
    schema = _public_schema()
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("maintenance_windows", schema=schema):
        return
    op.create_table(
        "maintenance_windows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "tenant_ids",
            postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column("notice_hours", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema=schema,
    )
    for col in ("starts_at", "ends_at"):
        op.create_index(
            f"ix_maintenance_windows_{col}",
            "maintenance_windows",
            [col],
            schema=schema,
        )


def downgrade():
    op.drop_table("maintenance_windows", schema=_public_schema())
