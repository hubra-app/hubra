"""Add is_default and default_value to setting

Revision ID: ad78d7415383
Revises: b7344d1d50a8
Create Date: 2026-07-02 12:04:50.835385

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ad78d7415383"
down_revision = "b7344d1d50a8"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("setting", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_default",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )
        batch_op.add_column(sa.Column("default_value", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("setting", schema=None) as batch_op:
        batch_op.drop_column("default_value")
        batch_op.drop_column("is_default")
