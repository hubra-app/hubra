"""add member fields phone mobile birthday membership_type membership_until emergency_contact custom_fields deleted_at

Revision ID: 5ad9717c8742
Revises: 40ce7d31d29e
Create Date: 2026-07-10 13:28:02.769369

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "5ad9717c8742"
down_revision = "40ce7d31d29e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("members", schema=None) as batch_op:
        batch_op.add_column(sa.Column("phone", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("mobile", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("birthday", sa.Date(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "membership_type",
                sa.String(length=50),
                nullable=False,
                server_default="regular",
            )
        )
        batch_op.add_column(sa.Column("membership_until", sa.Date(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "emergency_contact",
                postgresql.JSONB(astext_type=sa.Text()).with_variant(
                    sa.JSON(), "sqlite"
                ),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "custom_fields",
                postgresql.JSONB(astext_type=sa.Text()).with_variant(
                    sa.JSON(), "sqlite"
                ),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("members", schema=None) as batch_op:
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("custom_fields")
        batch_op.drop_column("emergency_contact")
        batch_op.drop_column("membership_until")
        batch_op.drop_column("membership_type")
        batch_op.drop_column("birthday")
        batch_op.drop_column("mobile")
        batch_op.drop_column("phone")
