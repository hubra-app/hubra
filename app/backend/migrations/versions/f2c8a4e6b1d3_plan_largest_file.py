"""plan: largest file a club can upload

Revision ID: f2c8a4e6b1d3
Revises: 0ae688271cd5
Create Date: 2026-11-11 09:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f2c8a4e6b1d3"
down_revision = "0ae688271cd5"
branch_labels = None
depends_on = None


def upgrade():
    # Null: the platform default (files.max_mb), as before.
    with op.batch_alter_table("platform_plans", schema=None) as batch_op:
        batch_op.add_column(sa.Column("limit_file_mb", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("platform_plans", schema=None) as batch_op:
        batch_op.drop_column("limit_file_mb")
