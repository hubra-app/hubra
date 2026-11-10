"""Dashboards can be shared with chosen groups: dashboards.group_ids

Revision ID: c4e8a2f6d1b3
Revises: 449652170fd4
Create Date: 2026-11-10 11:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c4e8a2f6d1b3"
down_revision = "449652170fd4"
branch_labels = None
depends_on = None


def upgrade():
    # A shared dashboard with group ids is seen by those groups' members
    # only; none (or empty) means the whole club, as before.
    with op.batch_alter_table("dashboards", schema=None) as batch_op:
        batch_op.add_column(sa.Column("group_ids", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("dashboards", schema=None) as batch_op:
        batch_op.drop_column("group_ids")
