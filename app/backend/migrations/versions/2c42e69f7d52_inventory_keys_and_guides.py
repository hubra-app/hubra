"""inventory keys and guides: keys, key_handovers, inventory_items.guide/guide_url

Revision ID: 2c42e69f7d52
Revises: b1d2e3f4a5c6
Create Date: 2026-10-28 08:37:20.983704

"""

# revision identifiers, used by Alembic.
revision = "2c42e69f7d52"
down_revision = "b1d2e3f4a5c6"
branch_labels = None
depends_on = None


# The tables moved to the keys and guides plugins (plugins/ in the repository),
# which create them in their own migrations.  This revision stays so
# databases that already ran it keep upgrading; the plugin adopts the
# tables they have.


def upgrade():
    pass


def downgrade():
    pass
