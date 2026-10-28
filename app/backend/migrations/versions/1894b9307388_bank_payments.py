"""bank_payments: credits imported from camt.054 files (finance.bank module)

Revision ID: 1894b9307388
Revises: 00b3c85ca2fa
Create Date: 2026-10-28 09:05:24.524909

"""

# revision identifiers, used by Alembic.
revision = "1894b9307388"
down_revision = "00b3c85ca2fa"
branch_labels = None
depends_on = None


# The tables moved to the bank import plugin (plugins/ in the repository),
# which creates them in its own migrations.  This revision stays so
# databases that already ran it keep upgrading; the plugin adopts the
# tables they have.


def upgrade():
    pass


def downgrade():
    pass
