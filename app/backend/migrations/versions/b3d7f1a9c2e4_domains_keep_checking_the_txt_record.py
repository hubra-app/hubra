"""Domains keep checking the TXT record

Custom domains are now checked on their own and re-checked once they are
verified, so a domain records when its TXT record was last looked up and
last found. A domain nobody verified is no longer a club's primary one.

Revision ID: b3d7f1a9c2e4
Revises: a9c4e2f7d1b6
Create Date: 2026-10-30 17:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b3d7f1a9c2e4"
down_revision = "a9c4e2f7d1b6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("domains", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True)
        )
    op.execute(
        "UPDATE domains SET last_seen_at = verified_at WHERE verified = true"
    )
    op.execute("UPDATE domains SET is_primary = false WHERE verified = false")


def downgrade():
    with op.batch_alter_table("domains", schema=None) as batch_op:
        batch_op.drop_column("last_seen_at")
        batch_op.drop_column("last_checked_at")
