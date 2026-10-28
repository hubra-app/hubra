"""email_verifications: verification tokens move to the public schema

Email verification now happens on the SSO portal, where no club is selected,
so the tokens live once in public instead of in every club schema.  The old
per-club ``email_verification_tokens`` tables are dropped; links that were
still open stop working and the user asks for a new one after signing in.

Safe to run again per club (flask migrate-tenants): the new table goes to
public, once.  The old tables are dropped in every schema in one go, club
schemas first, because their id columns use the public table's sequence.

Revision ID: 7b2d4f6a8c10
Revises: 3a7c1e9d5b20
Create Date: 2026-10-28 14:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7b2d4f6a8c10"
down_revision = "3a7c1e9d5b20"
branch_labels = None
depends_on = None


def _public_schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def _has_table(table, schema):
    return sa.inspect(op.get_bind()).has_table(table, schema=schema)


def _schemas_with(table):
    """Every schema holding *table*, club schemas before public."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return [None] if _has_table(table, None) else []
    rows = bind.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = :t ORDER BY table_schema = 'public', table_schema"
        ),
        {"t": table},
    ).scalars()
    return list(rows)


def upgrade():
    schema = _public_schema()
    if not _has_table("email_verifications", schema):
        op.create_table(
            "email_verifications",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash"),
            schema=schema,
        )

    for old in _schemas_with("email_verification_tokens"):
        op.drop_table("email_verification_tokens", schema=old)


def downgrade():
    # The per-club tables come back with the next club provisioning or a
    # restore; only the public one is recreated here.
    schema = _public_schema()
    if not _has_table("email_verification_tokens", schema):
        op.create_table(
            "email_verification_tokens",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash"),
            schema=schema,
        )
    if _has_table("email_verifications", schema):
        op.drop_table("email_verifications", schema=schema)
