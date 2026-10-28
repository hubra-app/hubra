"""add member address columns

Revision ID: c9349c59585c
Revises: 998e219fe859
Create Date: 2026-07-07 11:27:26.572391

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c9349c59585c"
down_revision = "998e219fe859"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("members", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("address_street", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("address_house_no", sa.String(length=20), nullable=True)
        )
        batch_op.add_column(
            sa.Column("address_postal_code", sa.String(length=20), nullable=True)
        )
        batch_op.add_column(
            sa.Column("address_city", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "address_country",
                sa.String(length=2),
                nullable=False,
                server_default="CH",
            )
        )


def downgrade():
    with op.batch_alter_table("members", schema=None) as batch_op:
        batch_op.drop_column("address_country")
        batch_op.drop_column("address_city")
        batch_op.drop_column("address_postal_code")
        batch_op.drop_column("address_house_no")
        batch_op.drop_column("address_street")
