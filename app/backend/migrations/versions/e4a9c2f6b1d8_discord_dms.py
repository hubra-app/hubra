"""Discord direct messages: users.dm_prefs and known_devices.soft_hash

``users.dm_prefs`` holds what an account wants as a Discord direct message
from the Hubra bot outside a club (sign-in alerts, answers to its own
requests) and the one "mute all direct messages" switch.
``known_devices.soft_hash`` is a hash of browser, system, language, time
zone and IP network: when a browser lost its device cookie, a recent match
counts as a known device (no sign-in alert).

Public-schema only, so the revision is safe to run again per club
(flask migrate-tenants).

Revision ID: e4a9c2f6b1d8
Revises: a9c3e5f7b1d4
Create Date: 2026-11-05 22:30:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "e4a9c2f6b1d8"
down_revision = "a9c3e5f7b1d4"
branch_labels = None
depends_on = None


def _public_schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def _json():
    return postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def _columns(table, schema):
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table, schema=schema):
        return None
    return {c["name"] for c in inspector.get_columns(table, schema=schema)}


def upgrade():
    schema = _public_schema()
    have = _columns("users", schema)
    if have is not None and "dm_prefs" not in have:
        op.add_column("users", sa.Column("dm_prefs", _json(), nullable=True), schema=schema)
    have = _columns("known_devices", schema)
    if have is not None and "soft_hash" not in have:
        op.add_column(
            "known_devices",
            sa.Column("soft_hash", sa.String(length=64), nullable=True),
            schema=schema,
        )


def downgrade():
    schema = _public_schema()
    have = _columns("known_devices", schema)
    if have is not None and "soft_hash" in have:
        op.drop_column("known_devices", "soft_hash", schema=schema)
    have = _columns("users", schema)
    if have is not None and "dm_prefs" in have:
        op.drop_column("users", "dm_prefs", schema=schema)
