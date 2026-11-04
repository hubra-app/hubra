"""api_tokens

Bearer tokens for scripts, integrations and the Claude connector
(docs/api-tokens.md). The table lives in public, once: a request's token is
found before its club is known.

Safe to run again per club (flask migrate-tenants): the table goes to
public, once.

Revision ID: b4e8f2a6c1d9
Revises: d8a3f1c6b2e7
Create Date: 2026-11-04 11:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b4e8f2a6c1d9"
down_revision = "d8a3f1c6b2e7"
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
    if _has_table("api_tokens", schema):
        return
    op.create_table(
        "api_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=16), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("member_id", sa.Integer(), nullable=True),
        sa.Column("created_by_name", sa.String(length=255), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("last4", sa.String(length=4), nullable=False),
        sa.Column("scopes", _json(), nullable=False),
        sa.Column("allowed_ips", _json(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_name", sa.String(length=255), nullable=True),
        sa.Column("revoked_reason", sa.String(length=50), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_ip", sa.String(length=45), nullable=True),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "failed_attempts", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "failed_window_started_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=schema,
    )
    op.create_index(
        "ix_api_tokens_public_id", "api_tokens", ["public_id"], unique=True,
        schema=schema,
    )
    op.create_index("ix_api_tokens_user_id", "api_tokens", ["user_id"], schema=schema)
    op.create_index(
        "ix_api_tokens_tenant_id", "api_tokens", ["tenant_id"], schema=schema
    )


def downgrade():
    schema = _public_schema()
    if _has_table("api_tokens", schema):
        op.drop_table("api_tokens", schema=schema)
