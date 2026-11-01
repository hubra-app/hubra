"""merge heads b3f8d2a6c9e1 and b5d9e3f7a1c6

The plugin key purposes and the platform events migrations (#97, #98)
both built on e7c3a9d1f5b2. This joins them so ``flask db upgrade`` has one head
again.

Revision ID: d2a6f0c4e8b3
Revises: b3f8d2a6c9e1, b5d9e3f7a1c6
Create Date: 2026-11-01 11:10:00.000000

"""

# revision identifiers, used by Alembic.
revision = "d2a6f0c4e8b3"
down_revision = ("b3f8d2a6c9e1", "b5d9e3f7a1c6")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
