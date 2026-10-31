"""merge heads a7d3e9c1f5b2, c3f7a1e5d9b4, d3f7a1c9e5b2 and f2c8a4e6b1d9

Several PRs merged on 2026-10-31 each added migrations on their own branch
(group visibility, a merge of nav prefs and data keys, connected apps, the
calendar feed version); this joins them so ``flask db upgrade`` has one head
again.

Revision ID: e5a9c3f7b1d4
Revises: a7d3e9c1f5b2, c3f7a1e5d9b4, d3f7a1c9e5b2, f2c8a4e6b1d9
Create Date: 2026-10-31 11:10:00.000000

"""

# revision identifiers, used by Alembic.
revision = "e5a9c3f7b1d4"
down_revision = ("a7d3e9c1f5b2", "c3f7a1e5d9b4", "d3f7a1c9e5b2", "f2c8a4e6b1d9")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
