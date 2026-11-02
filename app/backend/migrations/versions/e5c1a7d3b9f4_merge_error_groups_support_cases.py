"""merge heads d7a3c9e1f5b2 and f2b7d4a9c3e1

#148 (error groups) and #136 (support cases) both branched off
c4f8a2d6e9b1 and left two heads on main; this joins them so
``flask db upgrade`` has one head again.

Revision ID: e5c1a7d3b9f4
Revises: d7a3c9e1f5b2, f2b7d4a9c3e1
Create Date: 2026-11-02 13:20:00.000000

"""

# revision identifiers, used by Alembic.
revision = "e5c1a7d3b9f4"
down_revision = ("d7a3c9e1f5b2", "f2b7d4a9c3e1")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
