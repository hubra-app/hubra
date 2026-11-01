"""merge heads f2b6d8a1c4e7 and ee771f92971b

Both branched from b8e4d2a6f1c3: the known devices / two-factor / passkeys
chain and the recurring transactions / invoice periods chain. This joins
them so ``flask db upgrade`` has one head again.

Revision ID: c9d1e5a3f7b2
Revises: f2b6d8a1c4e7, ee771f92971b
Create Date: 2026-11-01 09:30:00.000000

"""

# revision identifiers, used by Alembic.
revision = "c9d1e5a3f7b2"
down_revision = ("f2b6d8a1c4e7", "ee771f92971b")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
