"""account_sessions.sudo_until (step-up for destructive platform actions).

Safe to run again per club (flask apply-tenant-migrations): the column goes
to the public table, once.

Revision ID: a7c4e9f2b6d1
Revises: f4a8c2e6b9d1
Create Date: 2026-11-01

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a7c4e9f2b6d1"
down_revision = "f4a8c2e6b9d1"
branch_labels = None
depends_on = None


def _public_schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def _has_column() -> bool:
    inspector = sa.inspect(op.get_bind())
    schema = _public_schema()
    if not inspector.has_table("account_sessions", schema=schema):
        return True  # nothing to do (fresh DB builds it from the model)
    return any(
        c["name"] == "sudo_until"
        for c in inspector.get_columns("account_sessions", schema=schema)
    )


def upgrade():
    if _has_column():
        return
    op.add_column(
        "account_sessions",
        sa.Column("sudo_until", sa.DateTime(timezone=True), nullable=True),
        schema=_public_schema(),
    )


def downgrade():
    if not _has_column():
        return
    op.drop_column("account_sessions", "sudo_until", schema=_public_schema())
