"""platform_settings: instance-wide settings such as the mail relay

Public-schema table only, so the revision is safe to run again per club
(flask migrate-tenants): the table goes to public, once.  Starts empty;
every key falls back to its env default until a platform manager sets it.

Revision ID: 3a7c1e9d5b20
Revises: 202ee240e1d8
Create Date: 2026-10-28 13:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3a7c1e9d5b20"
down_revision = "202ee240e1d8"
branch_labels = None
depends_on = None


def _public_schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def _has_table(table, schema):
    return sa.inspect(op.get_bind()).has_table(table, schema=schema)


def upgrade():
    schema = _public_schema()
    if not _has_table("platform_settings", schema):
        op.create_table(
            "platform_settings",
            sa.Column("key", sa.String(length=255), nullable=False),
            sa.Column("value", sa.Text(), nullable=True),
            sa.Column("secret", sa.Boolean(), nullable=False),
            sa.Column("updated_by", sa.Integer(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("key"),
            schema=schema,
        )


def downgrade():
    schema = _public_schema()
    if _has_table("platform_settings", schema):
        op.drop_table("platform_settings", schema=schema)
