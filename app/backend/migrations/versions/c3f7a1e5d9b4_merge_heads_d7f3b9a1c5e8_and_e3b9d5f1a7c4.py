"""merge heads d7f3b9a1c5e8 and e3b9d5f1a7c4

#77 (users.nav_prefs) and #86 (a data key per club) each added a migration
on their own branch; this joins them so ``flask db upgrade`` has one head
again.

Revision ID: c3f7a1e5d9b4
Revises: d7f3b9a1c5e8, e3b9d5f1a7c4
Create Date: 2026-10-31 10:20:00.000000

"""

# revision identifiers, used by Alembic.
revision = "c3f7a1e5d9b4"
down_revision = ("d7f3b9a1c5e8", "e3b9d5f1a7c4")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
