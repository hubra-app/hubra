"""merge heads after #85 and #87

#85 (membership invoice periods) and #87 (passkeys) each built on the
shared join b8e4d2a6f1c3, so main ended in two heads. This joins them so
``flask db upgrade`` has one head again. Open pull requests carry this same
file and build on it.

Revision ID: b4e8c2a6d0f3
Revises: ee771f92971b, f2b6d8a1c4e7
Create Date: 2026-11-01 09:30:00.000000

"""

# revision identifiers, used by Alembic.
revision = "b4e8c2a6d0f3"
down_revision = ("ee771f92971b", "f2b6d8a1c4e7")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
