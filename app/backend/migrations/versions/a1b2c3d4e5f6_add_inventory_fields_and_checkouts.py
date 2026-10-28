"""add inventory fields and checkouts table

Revision ID: a1b2c3d4e5f6
Revises: fc85792b5d9a
Create Date: 2026-07-10 14:45:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "fc85792b5d9a"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("inventory_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("purchase_date", sa.Date(), nullable=True))
        batch_op.add_column(
            sa.Column("purchase_cost", sa.Numeric(precision=10, scale=2), nullable=True)
        )
        batch_op.add_column(
            sa.Column("current_value", sa.Numeric(precision=10, scale=2), nullable=True)
        )
        batch_op.add_column(sa.Column("location", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column("serial_number", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("barcode_id", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "documents",
                postgresql.JSONB(astext_type=sa.Text()).with_variant(
                    sa.JSON(), "sqlite"
                ),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("image_url", sa.String(length=500), nullable=True)
        )
        batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
        )

    op.create_table(
        "inventory_checkouts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("checked_out_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expected_return_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("condition_notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["item_id"], ["inventory_items.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("inventory_checkouts")

    with op.batch_alter_table("inventory_items", schema=None) as batch_op:
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("notes")
        batch_op.drop_column("image_url")
        batch_op.drop_column("documents")
        batch_op.drop_column("barcode_id")
        batch_op.drop_column("serial_number")
        batch_op.drop_column("location")
        batch_op.drop_column("current_value")
        batch_op.drop_column("purchase_cost")
        batch_op.drop_column("purchase_date")
