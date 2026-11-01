"""platform_events: the platform's event log (mail sent/failed, relay
checks, system alerts); users.platform_alerts: which alert mails a
platform admin gets

Public-schema only, so the revision is safe to run again per club
(flask migrate-tenants): the table goes to public, once.

Revision ID: b5d9e3f7a1c6
Revises: e7c3a9d1f5b2
Create Date: 2026-11-01 10:30:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "b5d9e3f7a1c6"
down_revision = "e7c3a9d1f5b2"
branch_labels = None
depends_on = None


def _public_schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def _json():
    return postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade():
    schema = _public_schema()
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("platform_events", schema=schema):
        op.create_table(
            "platform_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("category", sa.String(length=20), nullable=False),
            sa.Column("kind", sa.String(length=50), nullable=False),
            sa.Column("level", sa.String(length=10), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=True),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("details", _json(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            schema=schema,
        )
        for col in ("created_at", "category", "kind"):
            op.create_index(
                f"ix_platform_events_{col}",
                "platform_events",
                [col],
                schema=schema,
            )

    have = {c["name"] for c in inspector.get_columns("users", schema=schema)}
    if "platform_alerts" not in have:
        op.add_column(
            "users",
            sa.Column("platform_alerts", _json(), nullable=True),
            schema=schema,
        )


def downgrade():
    schema = _public_schema()
    op.drop_column("users", "platform_alerts", schema=schema)
    op.drop_table("platform_events", schema=schema)
