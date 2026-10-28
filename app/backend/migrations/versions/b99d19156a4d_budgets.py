"""budgets: budgets and budget_lines (finance.budgets module)

Revision ID: b99d19156a4d
Revises: 2c42e69f7d52
Create Date: 2026-10-28 08:43:49.031744

"""

# revision identifiers, used by Alembic.
revision = "b99d19156a4d"
down_revision = "2c42e69f7d52"
branch_labels = None
depends_on = None


# The tables moved to the budgets plugin (plugins/ in the repository),
# which creates them in its own migrations.  This revision stays so
# databases that already ran it keep upgrading; the plugin adopts the
# tables they have.


def upgrade():
    pass


def downgrade():
    pass
