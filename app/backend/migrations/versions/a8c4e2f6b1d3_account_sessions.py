"""account_sessions: sign-ins to the account itself (SSO portal)

Signing in on the SSO portal opens no club, so it left no Session row and
the account page's session list stayed empty.  These sign-ins are recorded
once, in public; club sign-ins stay in the club schemas.

Safe to run again per club (flask migrate-tenants): the table goes to
public, once.

Revision ID: a8c4e2f6b1d3
Revises: e5a1c7f3b9d4
Create Date: 2026-10-30 08:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a8c4e2f6b1d3"
down_revision = "e5a1c7f3b9d4"
branch_labels = None
depends_on = None


def _public_schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def _has_table(table, schema):
    return sa.inspect(op.get_bind()).has_table(table, schema=schema)


def upgrade():
    schema = _public_schema()
    if _has_table("account_sessions", schema):
        return
    op.create_table(
        "account_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("browser_family", sa.String(length=50), nullable=True),
        sa.Column("platform", sa.String(length=50), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema=schema,
    )
    op.create_index(
        "ix_account_sessions_user_id", "account_sessions", ["user_id"], schema=schema
    )


def downgrade():
    schema = _public_schema()
    if _has_table("account_sessions", schema):
        op.drop_table("account_sessions", schema=schema)
