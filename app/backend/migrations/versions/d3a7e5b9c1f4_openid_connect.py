"""openid_connect

Sign in with Hubra (docs/oidc.md): club apps (oauth_clients.tenant_id),
the nonce and sign-in time on oauth_codes, and the agreed OAuth scopes on
api_tokens. All in public, once (safe to run again per club).

Revision ID: d3a7e5b9c1f4
Revises: e8b2d4f6a1c3
Create Date: 2026-11-05 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "d3a7e5b9c1f4"
down_revision = "e8b2d4f6a1c3"
branch_labels = None
depends_on = None


def _public_schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def _columns(table, schema):
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table, schema=schema)}


def upgrade():
    schema = _public_schema()
    have = _columns("oauth_clients", schema)
    if "tenant_id" not in have:
        with op.batch_alter_table("oauth_clients", schema=schema) as batch:
            batch.add_column(sa.Column("tenant_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(
                "fk_oauth_clients_tenant_id",
                "tenants",
                ["tenant_id"],
                ["id"],
                ondelete="CASCADE",
                referent_schema=schema,
            )
            batch.create_index("ix_oauth_clients_tenant_id", ["tenant_id"])
    have = _columns("oauth_codes", schema)
    missing = [
        c
        for c in (
            sa.Column("nonce", sa.String(length=255), nullable=True),
            sa.Column("auth_time", sa.DateTime(timezone=True), nullable=True),
        )
        if c.name not in have
    ]
    if missing:
        with op.batch_alter_table("oauth_codes", schema=schema) as batch:
            for col in missing:
                batch.add_column(col)
    if "oauth_scope" not in _columns("api_tokens", schema):
        with op.batch_alter_table("api_tokens", schema=schema) as batch:
            batch.add_column(sa.Column("oauth_scope", sa.String(length=100), nullable=True))


def downgrade():
    schema = _public_schema()
    if "oauth_scope" in _columns("api_tokens", schema):
        with op.batch_alter_table("api_tokens", schema=schema) as batch:
            batch.drop_column("oauth_scope")
    have = _columns("oauth_codes", schema)
    with op.batch_alter_table("oauth_codes", schema=schema) as batch:
        for name in ("auth_time", "nonce"):
            if name in have:
                batch.drop_column(name)
    if "tenant_id" in _columns("oauth_clients", schema):
        with op.batch_alter_table("oauth_clients", schema=schema) as batch:
            batch.drop_index("ix_oauth_clients_tenant_id")
            batch.drop_constraint("fk_oauth_clients_tenant_id", type_="foreignkey")
            batch.drop_column("tenant_id")
