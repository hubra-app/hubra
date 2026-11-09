"""platform_plans.selectable: clubs may pick the plan themselves, apart from
``public`` (shown on the website, hubra#261)

Existing plans keep what they did: a public plan stays selectable.
Public-schema only, so the revision is safe to run again per club
(flask migrate-tenants).

Revision ID: b3f9d1a7e5c2
Revises: e9c4a1f7b3d5
Create Date: 2026-11-09 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b3f9d1a7e5c2"
down_revision = "e9c4a1f7b3d5"
branch_labels = None
depends_on = None


def _public_schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def upgrade():
    schema = _public_schema()
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("platform_plans", schema=schema):
        return
    cols = {c["name"] for c in inspector.get_columns("platform_plans", schema=schema)}
    if "selectable" in cols:
        return
    op.add_column(
        "platform_plans",
        sa.Column(
            "selectable", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        schema=schema,
    )
    table = f"{schema}.platform_plans" if schema else "platform_plans"
    op.execute(f'UPDATE {table} SET selectable = "public"')


def downgrade():
    op.drop_column("platform_plans", "selectable", schema=_public_schema())
