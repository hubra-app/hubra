"""merge heads a7c4e9f2b6d1 and a6e2c8f4b1d7

#102 shipped merge migration a6e2c8f4b1d7 (joining #97 and #98) while the
web-push migration already joined the same two revisions, and sudo_until
(#103) built on the web-push line. That left main with two heads; this
joins them. Both branches are no-op merges, so any database state upgrades.

Revision ID: c8d1f4a7e2b9
Revises: a7c4e9f2b6d1, a6e2c8f4b1d7
Create Date: 2026-11-01 15:10:00.000000

"""

# revision identifiers, used by Alembic.
revision = "c8d1f4a7e2b9"
down_revision = ("a7c4e9f2b6d1", "a6e2c8f4b1d7")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
