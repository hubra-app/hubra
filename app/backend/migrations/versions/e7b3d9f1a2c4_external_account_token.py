"""Keep a linked Discord account's OAuth token for Linked Roles

``external_accounts.token_encrypted`` holds the person's access and refresh
token (encrypted with the platform key), so Hubra can keep their Discord
role connection ("member of a Hubra club") up to date. Only in public.

Revision ID: e7b3d9f1a2c4
Revises: d6f2b8e4a1c7
Create Date: 2026-11-02 09:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "e7b3d9f1a2c4"
down_revision = "d6f2b8e4a1c7"
branch_labels = None
depends_on = None


def _schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def upgrade():
    schema = _schema()
    have = {
        c["name"]
        for c in sa.inspect(op.get_bind()).get_columns(
            "external_accounts", schema=schema
        )
    }
    if "token_encrypted" not in have:
        op.add_column(
            "external_accounts",
            sa.Column("token_encrypted", sa.Text(), nullable=True),
            schema=schema,
        )


def downgrade():
    schema = _schema()
    have = {
        c["name"]
        for c in sa.inspect(op.get_bind()).get_columns(
            "external_accounts", schema=schema
        )
    }
    if "token_encrypted" in have:
        op.drop_column("external_accounts", "token_encrypted", schema=schema)
