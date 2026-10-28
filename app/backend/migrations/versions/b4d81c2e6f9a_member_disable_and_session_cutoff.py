"""Disabling is per club; an account can end all its sessions

``members.disabled_at`` replaces writing ``users.is_disabled`` from a club:
a club switches a member off in that club only.  The column is added to the
template table in public and to every club schema.

``users.tokens_valid_after`` ends every session of an account at once
(password reset, password set by an admin, account disabled).

Members a club had disabled through ``users.is_disabled`` keep that flag;
a platform manager re-enables the account if it should work elsewhere.

Revision ID: b4d81c2e6f9a
Revises: e8f3b1d5c7a2
Create Date: 2026-10-28 20:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b4d81c2e6f9a"
down_revision = "e8f3b1d5c7a2"
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
        have = {c["name"] for c in inspector.get_columns("members", schema=schema)}
        if "disabled_at" not in have:
            op.add_column(
                "members",
                sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
                schema=schema,
            )
    have = {c["name"] for c in inspector.get_columns("users")}
    if "tokens_valid_after" not in have:
        op.add_column(
            "users",
            sa.Column("tokens_valid_after", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    have = {c["name"] for c in inspector.get_columns("users")}
    if "tokens_valid_after" in have:
        op.drop_column("users", "tokens_valid_after")
    for schema in _schemas():
        have = {c["name"] for c in inspector.get_columns("members", schema=schema)}
        if "disabled_at" in have:
            op.drop_column("members", "disabled_at", schema=schema)
