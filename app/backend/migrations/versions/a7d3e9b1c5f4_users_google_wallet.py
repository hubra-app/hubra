"""users.google_wallet_object and users.google_wallet_hash

The member badge's pass in Google Wallet (core/services/google_wallet.py):
the pass's object id once the person saved it, and a hash of what it shows.

Public-schema only, so the revision is safe to run again per club
(flask migrate-tenants).

Revision ID: a7d3e9b1c5f4
Revises: e3a7c9f1b5d2
Create Date: 2026-11-10 08:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a7d3e9b1c5f4"
down_revision = "e3a7c9f1b5d2"
branch_labels = None
depends_on = None


def _public_schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def _columns(table, schema):
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table, schema=schema):
        return None
    return {c["name"] for c in inspector.get_columns(table, schema=schema)}


def upgrade():
    schema = _public_schema()
    have = _columns("users", schema)
    if have is not None and "google_wallet_object" not in have:
        op.add_column(
            "users",
            sa.Column("google_wallet_object", sa.String(length=128), nullable=True),
            schema=schema,
        )
    if have is not None and "google_wallet_hash" not in have:
        op.add_column(
            "users",
            sa.Column("google_wallet_hash", sa.String(length=64), nullable=True),
            schema=schema,
        )


def downgrade():
    schema = _public_schema()
    have = _columns("users", schema)
    for col in ("google_wallet_hash", "google_wallet_object"):
        if have is not None and col in have:
            op.drop_column("users", col, schema=schema)
