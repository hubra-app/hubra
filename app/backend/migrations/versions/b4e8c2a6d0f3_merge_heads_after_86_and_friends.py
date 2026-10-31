"""merge heads a7d3e9c1f5b2, c3f7a1e5d9b4, d3f7a1c9e5b2 and f2c8a4e6b1d9

#77 and #86 left main with two heads (d7f3b9a1c5e8, e3b9d5f1a7c4). Four
branches then each joined those two on their own: the groups visibility
migration, the connected apps migration, the calendar feed version
migration, and a plain merge. Together that is four heads again, and
``flask db upgrade`` refuses to run. This joins them.

Revision ID: b4e8c2a6d0f3
Revises: a7d3e9c1f5b2, c3f7a1e5d9b4, d3f7a1c9e5b2, f2c8a4e6b1d9
Create Date: 2026-10-31 11:00:00.000000

"""

# revision identifiers, used by Alembic.
revision = "b4e8c2a6d0f3"
down_revision = ("a7d3e9c1f5b2", "c3f7a1e5d9b4", "d3f7a1c9e5b2", "f2c8a4e6b1d9")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
