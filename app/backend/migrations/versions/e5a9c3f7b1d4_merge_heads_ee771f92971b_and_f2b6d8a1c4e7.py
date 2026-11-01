"""merge heads ee771f92971b and f2b6d8a1c4e7

Membership invoice periods and passkeys each added a migration on their own
branch; this joins them so ``flask db upgrade`` has one head again.

Revision ID: e5a9c3f7b1d4
Revises: ee771f92971b, f2b6d8a1c4e7
Create Date: 2026-11-01 09:30:00.000000

"""

# revision identifiers, used by Alembic.
revision = "e5a9c3f7b1d4"
down_revision = ("ee771f92971b", "f2b6d8a1c4e7")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
