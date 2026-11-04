"""data_requests: data protection requests (copy or deletion) per club and
when they were handled

Public-schema only, so the revision is safe to run again per club
(flask migrate-tenants): the table goes to public, once.

Revision ID: f4a8c2e6d0b3
Revises: e5c1a7d3b9f4
Create Date: 2026-11-02 15:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "f4a8c2e6d0b3"
down_revision = "e5c1a7d3b9f4"
branch_labels = None
depends_on = None


def _public_schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def upgrade():
    schema = _public_schema()
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("data_requests", schema=schema):
        return
    json = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")
    op.create_table(
        "data_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("tenant_name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("subject_name", sa.String(200), nullable=False),
        sa.Column("subject_email", sa.String(320), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=True),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("received_via", sa.String(100), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("handled_by", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("result", json, nullable=True),
        sa.Column("exports", json, nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema=schema,
    )
    for col in ("tenant_id", "status", "due_on"):
        op.create_index(
            f"ix_data_requests_{col}", "data_requests", [col], schema=schema
        )


def downgrade():
    op.drop_table("data_requests", schema=_public_schema())
