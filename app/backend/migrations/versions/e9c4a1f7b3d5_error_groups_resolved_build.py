"""error_groups.resolved_build: the build an error was marked fixed in

Upgrades mark open errors that did not happen on the new build as fixed
(services.error_tracker.resolve_after_upgrade); manage shows the build.

Public-schema only, so the revision is safe to run again per club
(flask migrate-tenants).

Revision ID: e9c4a1f7b3d5
Revises: d8b2f4a6c1e3
Create Date: 2026-11-09 09:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e9c4a1f7b3d5"
down_revision = "d8b2f4a6c1e3"
branch_labels = None
depends_on = None


def _public_schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def upgrade():
    schema = _public_schema()
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("error_groups", schema=schema):
        return
    cols = {c["name"] for c in inspector.get_columns("error_groups", schema=schema)}
    if "resolved_build" not in cols:
        op.add_column(
            "error_groups",
            sa.Column("resolved_build", sa.String(80), nullable=True),
            schema=schema,
        )


def downgrade():
    op.drop_column("error_groups", "resolved_build", schema=_public_schema())
