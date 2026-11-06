"""merge heads a5c9e3b7d1f2 and a5d1f7c3e9b2

#233 (privacy self-service) and #229 (support cases on Discord) both
branched off the same revision and left two heads on main; this joins them
so ``flask db upgrade`` has one head again.

Revision ID: b3e7a1c5d9f2
Revises: a5c9e3b7d1f2, a5d1f7c3e9b2
Create Date: 2026-11-06 09:30:00.000000

"""

# revision identifiers, used by Alembic.
revision = "b3e7a1c5d9f2"
down_revision = ("a5c9e3b7d1f2", "a5d1f7c3e9b2")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
