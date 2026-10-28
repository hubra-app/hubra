"""budgets and budget_lines

Databases that ran Hubra's own revision b99d19156a4d have the tables
already; they are kept as they are.

Revision ID: 8c2cf6ad6e72
Revises:
Create Date: 2026-10-28 10:00:00

"""

from alembic import op
import sqlalchemy as sa

from hubra.core.plugins.ops import has_table


# revision identifiers, used by Alembic.
revision = "8c2cf6ad6e72"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    if has_table("budgets"):
        return
    op.create_table(
        "budgets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("year", "name", name="uq_budget_year_name"),
    )
    with op.batch_alter_table("budgets", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_budgets_year"), ["year"], unique=False)

    op.create_table(
        "budget_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("budget_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("planned", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["budget_id"], ["budgets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["category_id"], ["transaction_categories.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "budget_id", "category_id", "kind", name="uq_budget_line_category"
        ),
    )


def downgrade():
    # Dropping a table drops its indexes; club schemas cloned from public
    # name them differently, so they are not dropped by name.
    op.drop_table("budget_lines")
    op.drop_table("budgets")
