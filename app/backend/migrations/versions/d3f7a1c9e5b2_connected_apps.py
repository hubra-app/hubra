"""connected_apps, connected_app_events, external_accounts

A club's links to outside services (a Discord server) and a person's
linked outside accounts (their Discord user). Requests from those services
carry only the outside id, so the tables live in public, once.

Safe to run again per club (flask migrate-tenants): the tables go to
public, once.

Revision ID: d3f7a1c9e5b2
Revises: d7f3b9a1c5e8, e3b9d5f1a7c4
Create Date: 2026-10-31 07:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "d3f7a1c9e5b2"
# Also joins the two heads main had (users nav prefs, data keys).
down_revision = ("d7f3b9a1c5e8", "e3b9d5f1a7c4")
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
    if not _has_table("connected_apps", schema):
        op.create_table(
            "connected_apps",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=50), nullable=False),
            sa.Column("external_id", sa.String(length=100), nullable=False),
            sa.Column("label", sa.String(length=200), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("scopes", _json(), nullable=True),
            sa.Column("config", _json(), nullable=True),
            sa.Column("secret_encrypted", sa.Text(), nullable=True),
            sa.Column("created_by_member_id", sa.Integer(), nullable=True),
            sa.Column("created_by_name", sa.String(length=255), nullable=False),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.String(length=500), nullable=True),
            sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_by_name", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            schema=schema,
        )
        op.create_index(
            "ix_connected_apps_tenant_id",
            "connected_apps",
            ["tenant_id"],
            schema=schema,
        )
        op.create_index(
            "uq_connected_apps_active_external",
            "connected_apps",
            ["provider", "external_id"],
            unique=True,
            schema=schema,
            postgresql_where=sa.text("status = 'active'"),
            sqlite_where=sa.text("status = 'active'"),
        )
    if not _has_table("connected_app_events", schema):
        op.create_table(
            "connected_app_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("connection_id", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(length=50), nullable=False),
            sa.Column("ok", sa.Boolean(), nullable=False),
            sa.Column("detail", sa.String(length=500), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["connection_id"], ["connected_apps.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            schema=schema,
        )
        op.create_index(
            "ix_connected_app_events_connection_id",
            "connected_app_events",
            ["connection_id"],
            schema=schema,
        )
    if not _has_table("external_accounts", schema):
        op.create_table(
            "external_accounts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=50), nullable=False),
            sa.Column("external_id", sa.String(length=100), nullable=False),
            sa.Column("username", sa.String(length=200), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("provider", "external_id", name="uq_external_account"),
            sa.UniqueConstraint("user_id", "provider", name="uq_external_account_user"),
            schema=schema,
        )
        op.create_index(
            "ix_external_accounts_user_id",
            "external_accounts",
            ["user_id"],
            schema=schema,
        )


def downgrade():
    schema = _public_schema()
    for table in ("external_accounts", "connected_app_events", "connected_apps"):
        if _has_table(table, schema):
            op.drop_table(table, schema=schema)
