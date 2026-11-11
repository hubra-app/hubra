"""sessions.account_sid: the account sign-in a club session was opened from.

The account Sessions page (SSO) lists only the account's own sign-ins and
shows the clubs opened from each as tags; this column links them. No foreign
key: club sessions live in the club schema, account sign-ins in public.

Safe to run again per club (flask apply-tenant-migrations).

Revision ID: b3e7d1f5a9c2
Revises: 0afbd6a82c42
Create Date: 2026-11-11

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b3e7d1f5a9c2"
down_revision = "0afbd6a82c42"
branch_labels = None
depends_on = None


def _columns() -> set[str] | None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("sessions"):
        return None
    return {c["name"] for c in inspector.get_columns("sessions")}


def upgrade():
    columns = _columns()
    if columns is None or "account_sid" in columns:
        return
    op.add_column("sessions", sa.Column("account_sid", sa.Integer(), nullable=True))
    op.create_index("ix_sessions_account_sid", "sessions", ["account_sid"])


def downgrade():
    columns = _columns()
    if columns is None or "account_sid" not in columns:
        return
    op.drop_index("ix_sessions_account_sid", table_name="sessions")
    op.drop_column("sessions", "account_sid")
