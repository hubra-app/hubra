"""rename retention_days to retention ms and add from_whitelist column

Revision ID: 73c797dd2e47
Revises: 1932707ee869
Create Date: 2026-07-03 12:57:53.312806

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "73c797dd2e47"
down_revision = "1932707ee869"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("managed_mail_addresses", schema=None) as batch_op:
        batch_op.add_column(sa.Column("retention", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("from_whitelist", sa.Text(), nullable=True))

    op.execute(
        "UPDATE managed_mail_addresses "
        "SET retention = retention_days * 86400000 "
        "WHERE retention_days IS NOT NULL AND retention_days > 0"
    )

    with op.batch_alter_table("managed_mail_addresses", schema=None) as batch_op:
        batch_op.drop_column("retention_days")


def downgrade():
    with op.batch_alter_table("managed_mail_addresses", schema=None) as batch_op:
        batch_op.add_column(sa.Column("retention_days", sa.INTEGER(), nullable=True))

    op.execute(
        "UPDATE managed_mail_addresses "
        "SET retention_days = CAST(retention / 86400000 AS INTEGER) "
        "WHERE retention IS NOT NULL AND retention > 0"
    )

    with op.batch_alter_table("managed_mail_addresses", schema=None) as batch_op:
        batch_op.drop_column("from_whitelist")
        batch_op.drop_column("retention")
