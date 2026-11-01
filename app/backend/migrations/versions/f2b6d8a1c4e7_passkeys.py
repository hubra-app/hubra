"""passkeys: WebAuthn credentials an account signs in with

Safe to run again per club (flask migrate-tenants): the table goes to
public, once.

Revision ID: f2b6d8a1c4e7
Revises: e7a2c9f4b8d1
Create Date: 2026-10-31 09:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f2b6d8a1c4e7"
down_revision = "e7a2c9f4b8d1"
branch_labels = None
depends_on = None


def _public_schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def _has_table(table, schema):
    return sa.inspect(op.get_bind()).has_table(table, schema=schema)


def upgrade():
    schema = _public_schema()
    if _has_table("passkeys", schema):
        return
    op.create_table(
        "passkeys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("credential_id", sa.String(length=1400), nullable=False),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("sign_count", sa.Integer(), nullable=False),
        sa.Column("transports", sa.String(length=200), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("credential_id"),
        schema=schema,
    )
    op.create_index("ix_passkeys_user_id", "passkeys", ["user_id"], schema=schema)


def downgrade():
    schema = _public_schema()
    if _has_table("passkeys", schema):
        op.drop_table("passkeys", schema=schema)
