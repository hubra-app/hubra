"""Join main's two heads: #99/#103 (web push, sudo_until) and #102 merged
the earlier pair in parallel, so the tree forked again. No schema changes.

Revision ID: c9e1f5a3b7d2
Revises: a7c4e9f2b6d1, a6e2c8f4b1d7
Create Date: 2026-11-01

"""

# revision identifiers, used by Alembic.
revision = "c9e1f5a3b7d2"
down_revision = ("a7c4e9f2b6d1", "a6e2c8f4b1d7")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
