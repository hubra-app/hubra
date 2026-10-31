"""A club can have its own backup public key

``tenants.backup_public_key``: an age public key club backups are encrypted
to, besides the install's ``BACKUP_PUBLIC_KEY``.

Revision ID: d1a7c3e9b5f2
Revises: c5e2a8d4f1b7
Create Date: 2026-10-31 07:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d1a7c3e9b5f2"
down_revision = "c5e2a8d4f1b7"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # tenants lives in public only; club schemas run this too.
        op.execute(
            "ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS backup_public_key text"
        )
        return
    have = {c["name"] for c in sa.inspect(bind).get_columns("tenants")}
    if "backup_public_key" not in have:
        op.add_column(
            "tenants", sa.Column("backup_public_key", sa.Text(), nullable=True)
        )


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE public.tenants DROP COLUMN IF EXISTS backup_public_key")
    else:
        op.drop_column("tenants", "backup_public_key")
