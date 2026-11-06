"""platform_plans.builds_on + platform_plans.club_ids: a plan that includes
the modules of the plan below it, and custom plans offered to chosen clubs

Public-schema only, so the revision is safe to run again per club
(flask migrate-tenants).

Revision ID: d8b2f4a6c1e3
Revises: c4e8a2f6b0d3
Create Date: 2026-11-06 16:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "d8b2f4a6c1e3"
down_revision = "c4e8a2f6b0d3"
branch_labels = None
depends_on = None


def _public_schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def _columns(inspector, table, schema):
    if not inspector.has_table(table, schema=schema):
        return None
    return {c["name"] for c in inspector.get_columns(table, schema=schema)}


def upgrade():
    schema = _public_schema()
    inspector = sa.inspect(op.get_bind())
    json = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")
    cols = _columns(inspector, "platform_plans", schema)
    if cols is None:
        return
    if "builds_on" not in cols:
        op.add_column(
            "platform_plans",
            sa.Column("builds_on", sa.String(40), nullable=True),
            schema=schema,
        )
    if "club_ids" not in cols:
        op.add_column(
            "platform_plans", sa.Column("club_ids", json, nullable=True), schema=schema
        )


def downgrade():
    schema = _public_schema()
    op.drop_column("platform_plans", "club_ids", schema=schema)
    op.drop_column("platform_plans", "builds_on", schema=schema)
