"""contract_outbox

The contract outbox (docs/contracts.md): plugin events and queued actions,
stored in the caller's transaction and delivered after it commits, with
retries. One table in public for every club; safe to run again per club.

Revision ID: a9c3e5f7b1d4
Revises: f2a6c8e4b1d7
Create Date: 2026-11-05 23:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a9c3e5f7b1d4"
down_revision = "f2a6c8e4b1d7"
branch_labels = None
depends_on = None


def _public_schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def _has_table(table, schema):
    return sa.inspect(op.get_bind()).has_table(table, schema=schema)


def _json():
    return postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade():
    schema = _public_schema()
    if _has_table("contract_outbox", schema):
        return
    op.create_table(
        "contract_outbox",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("uid", sa.String(length=36), nullable=False),
        sa.Column("message_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("module_code", sa.String(length=100), nullable=False),
        sa.Column("target", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("envelope", _json(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("uid"),
        schema=schema,
    )
    op.create_index(
        "ix_contract_outbox_message_id", "contract_outbox", ["message_id"], schema=schema
    )
    op.create_index(
        "ix_contract_outbox_due",
        "contract_outbox",
        ["status", "next_attempt_at"],
        schema=schema,
    )


def downgrade():
    schema = _public_schema()
    if _has_table("contract_outbox", schema):
        op.drop_table("contract_outbox", schema=schema)
