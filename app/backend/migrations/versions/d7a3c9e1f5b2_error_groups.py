"""error_groups: unexpected API errors grouped by type, route and code
location, with the builds they happened on

Public-schema only, so the revision is safe to run again per club
(flask migrate-tenants): the table goes to public, once.

Revision ID: d7a3c9e1f5b2
Revises: c4f8a2d6e9b1
Create Date: 2026-11-02 11:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "d7a3c9e1f5b2"
down_revision = "c4f8a2d6e9b1"
branch_labels = None
depends_on = None


def _public_schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def upgrade():
    schema = _public_schema()
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("error_groups", schema=schema):
        return
    op.create_table(
        "error_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(length=40), nullable=False),
        sa.Column("exc_type", sa.String(length=200), nullable=False),
        sa.Column("route", sa.String(length=300), nullable=False),
        sa.Column("location", sa.String(length=300), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("traceback", sa.Text(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_version", sa.String(length=50), nullable=True),
        sa.Column("first_commit", sa.String(length=40), nullable=True),
        sa.Column("last_version", sa.String(length=50), nullable=True),
        sa.Column("last_commit", sa.String(length=40), nullable=True),
        sa.Column(
            "builds",
            postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column("last_tenant_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Integer(), nullable=True),
        sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint"),
        schema=schema,
    )
    op.create_index(
        "ix_error_groups_last_seen", "error_groups", ["last_seen"], schema=schema
    )


def downgrade():
    op.drop_table("error_groups", schema=_public_schema())
