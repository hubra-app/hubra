"""merge heads a6e2c8f4b1d7 and a7c4e9f2b6d1

#102 (platform alerts, joined #97/#98) and #103 (account sessions
sudo_until, on #99's web-push head) both left a head on main; this joins
them so ``flask db upgrade`` has one head again.

Revision ID: c8e2a4f6d1b9
Revises: a6e2c8f4b1d7, a7c4e9f2b6d1
Create Date: 2026-11-01 15:00:00.000000

"""

# revision identifiers, used by Alembic.
revision = "c8e2a4f6d1b9"
down_revision = ("a6e2c8f4b1d7", "a7c4e9f2b6d1")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
