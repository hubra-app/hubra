"""oauth_apps

OAuth apps (docs/oauth.md): oauth_clients, oauth_codes, and the columns on
api_tokens that make a row a sign-in an app holds. All in public, once
(safe to run again per club).

Revision ID: c7f1a9e3b5d2
Revises: f1c7a3e9b5d2
Create Date: 2026-11-05 00:30:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c7f1a9e3b5d2"
down_revision = "f1c7a3e9b5d2"
branch_labels = None
depends_on = None


def _public_schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def _has_table(table, schema):
    return sa.inspect(op.get_bind()).has_table(table, schema=schema)


def _columns(table, schema):
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table, schema=schema)}


def _json():
    return postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade():
    schema = _public_schema()
    ref = f"{schema}." if schema else ""
    if not _has_table("oauth_clients", schema):
        op.create_table(
            "oauth_clients",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("client_id", sa.String(length=64), nullable=False),
            sa.Column("kind", sa.String(length=20), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
            sa.Column("client_uri", sa.String(length=500), nullable=True),
            sa.Column("redirect_uris", _json(), nullable=False),
            sa.Column("secret_hash", sa.String(length=64), nullable=True),
            sa.Column("secret_last4", sa.String(length=4), nullable=True),
            sa.Column("resources", _json(), nullable=False),
            sa.Column("scopes", _json(), nullable=False),
            sa.Column("created_by_name", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("created_ip", sa.String(length=45), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            schema=schema,
        )
        op.create_index(
            "ix_oauth_clients_client_id", "oauth_clients", ["client_id"], unique=True,
            schema=schema,
        )
    if not _has_table("oauth_codes", schema):
        op.create_table(
            "oauth_codes",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("code_hash", sa.String(length=64), nullable=False),
            sa.Column("client_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("kind", sa.String(length=20), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=True),
            sa.Column("member_id", sa.Integer(), nullable=True),
            sa.Column("scopes", _json(), nullable=False),
            sa.Column("oauth_scope", sa.String(length=100), nullable=False),
            sa.Column("resource", sa.String(length=500), nullable=False),
            sa.Column("redirect_uri", sa.String(length=1000), nullable=False),
            sa.Column("code_challenge", sa.String(length=128), nullable=False),
            sa.Column("days", sa.Integer(), nullable=False),
            sa.Column("created_by_name", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("token_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["client_id"], [f"{ref}oauth_clients.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["user_id"], [f"{ref}users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["tenant_id"], [f"{ref}tenants.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            schema=schema,
        )
        op.create_index(
            "ix_oauth_codes_code_hash", "oauth_codes", ["code_hash"], unique=True,
            schema=schema,
        )
    have = _columns("api_tokens", schema)
    new = [
        sa.Column("oauth_client_id", sa.Integer(), nullable=True),
        sa.Column("resource", sa.String(length=500), nullable=True),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("prev_secret_hash", sa.String(length=64), nullable=True),
        sa.Column("refresh_hash", sa.String(length=64), nullable=True),
        sa.Column("prev_refresh_hash", sa.String(length=64), nullable=True),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=True),
    ]
    missing = [c for c in new if c.name not in have]
    if missing:
        with op.batch_alter_table("api_tokens", schema=schema) as batch:
            for col in missing:
                batch.add_column(col)
            if any(c.name == "oauth_client_id" for c in missing):
                batch.create_foreign_key(
                    "fk_api_tokens_oauth_client_id",
                    "oauth_clients",
                    ["oauth_client_id"],
                    ["id"],
                    ondelete="CASCADE",
                    referent_schema=schema,
                )
                batch.create_index("ix_api_tokens_oauth_client_id", ["oauth_client_id"])


def downgrade():
    schema = _public_schema()
    have = _columns("api_tokens", schema)
    with op.batch_alter_table("api_tokens", schema=schema) as batch:
        if "oauth_client_id" in have:
            batch.drop_index("ix_api_tokens_oauth_client_id")
            batch.drop_constraint("fk_api_tokens_oauth_client_id", type_="foreignkey")
        for name in (
            "refreshed_at",
            "prev_refresh_hash",
            "refresh_hash",
            "prev_secret_hash",
            "access_expires_at",
            "resource",
            "oauth_client_id",
        ):
            if name in have:
                batch.drop_column(name)
    for table in ("oauth_codes", "oauth_clients"):
        if _has_table(table, schema):
            op.drop_table(table, schema=schema)
