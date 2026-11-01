"""merge heads b3f8d2a6c9e1 and b5d9e3f7a1c6

#97 (plugin key purposes) and #98 (platform events) both revised
e7c3a9d1f5b2 and were merged on the same morning; this joins them so
``flask db upgrade`` has one head again.

Revision ID: a6e2c8f4b1d7
Revises: b3f8d2a6c9e1, b5d9e3f7a1c6
Create Date: 2026-11-01 11:00:00.000000

"""

# revision identifiers, used by Alembic.
revision = "a6e2c8f4b1d7"
down_revision = ("b3f8d2a6c9e1", "b5d9e3f7a1c6")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
