"""Outgoing webhooks

``webhooks`` (address, encrypted secret, events) and
``webhook_deliveries`` (the latest deliveries of each). Added to the
template tables in public and to every club schema.

Revision ID: b8d2f6a4c9e1
Revises: e7c4a9b2d6f1
Create Date: 2026-11-05 19:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "b8d2f6a4c9e1"
down_revision = "e7c4a9b2d6f1"
branch_labels = None
depends_on = None


def _schemas():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return [None]
    rows = bind.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'members' ORDER BY table_schema"
        )
    ).scalars()
    return list(rows)


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        ref = f"{schema}." if schema else ""
        if not inspector.has_table("webhooks", schema=schema):
            op.create_table(
                "webhooks",
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("name", sa.String(100), nullable=False),
                sa.Column("url", sa.String(500), nullable=False),
                sa.Column("secret", sa.Text(), nullable=False),
                sa.Column("events", sa.JSON(), nullable=False),
                sa.Column("active", sa.Boolean(), nullable=False),
                sa.Column("failures", sa.Integer(), nullable=False),
                sa.Column("disabled_reason", sa.String(255), nullable=True),
                sa.Column(
                    "created_by",
                    sa.Integer(),
                    sa.ForeignKey(f"{ref}members.id", ondelete="SET NULL"),
                    nullable=True,
                ),
                sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                sa.Column(
                    "last_delivery_at", sa.DateTime(timezone=True), nullable=True
                ),
                schema=schema,
            )
        if not inspector.has_table("webhook_deliveries", schema=schema):
            op.create_table(
                "webhook_deliveries",
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column(
                    "webhook_id",
                    sa.Integer(),
                    sa.ForeignKey(f"{ref}webhooks.id", ondelete="CASCADE"),
                    nullable=False,
                ),
                sa.Column("uid", sa.String(36), nullable=False, unique=True),
                sa.Column("event", sa.String(64), nullable=False),
                sa.Column("body", sa.Text(), nullable=False),
                sa.Column("status", sa.String(20), nullable=False),
                sa.Column("attempts", sa.Integer(), nullable=False),
                sa.Column("response_status", sa.Integer(), nullable=True),
                sa.Column("error", sa.String(500), nullable=True),
                sa.Column("duration_ms", sa.Integer(), nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
                schema=schema,
            )
            op.create_index(
                "ix_webhook_deliveries_webhook_id",
                "webhook_deliveries",
                ["webhook_id"],
                schema=schema,
            )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        for table in ("webhook_deliveries", "webhooks"):
            if inspector.has_table(table, schema=schema):
                op.drop_table(table, schema=schema)
