"""merge heads d7a3c9e1f5b2 and f2b7d4a9c3e1

#148 (error groups) and the support cases migration both revised
c4f8a2d6e9b1 and reached main on the same day; this joins them so
``flask db upgrade`` has one head again.

Revision ID: e9b4c7a2d5f8
Revises: d7a3c9e1f5b2, f2b7d4a9c3e1
Create Date: 2026-11-02 14:30:00.000000

"""

# revision identifiers, used by Alembic.
revision = "e9b4c7a2d5f8"
down_revision = ("d7a3c9e1f5b2", "f2b7d4a9c3e1")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
