"""platform_plans.modules + platform_addons.price_unit: modules included in
a plan, and module prices that are flat, per member or per licence

Public-schema only, so the revision is safe to run again per club
(flask migrate-tenants).

Revision ID: c3d7a1e5f9b2
Revises: b6e2f8a4c0d9
Create Date: 2026-11-02 18:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "c3d7a1e5f9b2"
down_revision = "b6e2f8a4c0d9"
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
    if cols is not None and "modules" not in cols:
        op.add_column(
            "platform_plans", sa.Column("modules", json, nullable=True), schema=schema
        )
    cols = _columns(inspector, "platform_addons", schema)
    if cols is not None and "price_unit" not in cols:
        op.add_column(
            "platform_addons",
            sa.Column(
                "price_unit", sa.String(10), nullable=False, server_default="flat"
            ),
            schema=schema,
        )


def downgrade():
    schema = _public_schema()
    op.drop_column("platform_addons", "price_unit", schema=schema)
    op.drop_column("platform_plans", "modules", schema=schema)
