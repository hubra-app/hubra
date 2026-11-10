"""post channels

Revision ID: 6abe39566b6c
Revises: 2f36591533c8
Create Date: 2026-11-10 12:34:19.814236

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "6abe39566b6c"
down_revision = "2f36591533c8"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("posts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "channels",
                postgresql.JSONB(astext_type=sa.Text()).with_variant(
                    sa.JSON(), "sqlite"
                ),
                nullable=True,
            )
        )


def downgrade():
    with op.batch_alter_table("posts", schema=None) as batch_op:
        batch_op.drop_column("channels")
