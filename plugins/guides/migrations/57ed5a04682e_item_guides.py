"""item_guides: one usage guide per inventory item

Databases that ran Hubra's own revision 2c42e69f7d52 kept guides in
inventory_items.guide and guide_url; those move here.

Revision ID: 57ed5a04682e
Revises:
Create Date: 2026-10-28 10:00:00

"""

from alembic import op
import sqlalchemy as sa

from hubra.core.plugins.ops import columns, has_table


# revision identifiers, used by Alembic.
revision = "57ed5a04682e"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    if not has_table("item_guides"):
        op.create_table(
            "item_guides",
            sa.Column("item_id", sa.Integer(), nullable=False),
            sa.Column("guide", sa.Text(), nullable=True),
            sa.Column("guide_url", sa.String(length=500), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["item_id"], ["inventory_items.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("item_id"),
        )
    if {"guide", "guide_url"} <= columns("inventory_items"):
        op.execute(
            "INSERT INTO item_guides (item_id, guide, guide_url, updated_at) "
            "SELECT id, guide, guide_url, CURRENT_TIMESTAMP FROM inventory_items "
            "WHERE guide IS NOT NULL OR guide_url IS NOT NULL"
        )
        with op.batch_alter_table("inventory_items", schema=None) as batch_op:
            batch_op.drop_column("guide_url")
            batch_op.drop_column("guide")


def downgrade():
    # Dropping a table drops its indexes; club schemas cloned from public
    # name them differently, so they are not dropped by name.
    op.drop_table("item_guides")
