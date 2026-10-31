"""merge heads after #81, #84, #92 and #93

#84 (calendar feed version), #92 (group visibility), #93 (connected apps)
and the #77/#86 merge each joined main's two heads on their own branch, so
main ended in four heads. This joins them so ``flask db upgrade`` has one
head again. Open pull requests carry this same file and build on it.

Revision ID: b8e4d2a6f1c3
Revises: a7d3e9c1f5b2, c3f7a1e5d9b4, d3f7a1c9e5b2, f2c8a4e6b1d9
Create Date: 2026-10-31 10:50:00.000000

"""

# revision identifiers, used by Alembic.
revision = "b8e4d2a6f1c3"
down_revision = ("a7d3e9c1f5b2", "c3f7a1e5d9b4", "d3f7a1c9e5b2", "f2c8a4e6b1d9")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
