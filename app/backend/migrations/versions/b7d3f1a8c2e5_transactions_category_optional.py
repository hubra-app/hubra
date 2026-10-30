"""A transaction no longer needs a category

New clubs start without categories, so recording the first transaction
failed until someone made one. ``transactions.category_id`` becomes
nullable on the template table in public and on every club schema.

Revision ID: b7d3f1a8c2e5
Revises: a9c4e2f7d1b6
Create Date: 2026-10-30 16:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7d3f1a8c2e5"
down_revision = "a9c4e2f7d1b6"
branch_labels = None
depends_on = None


def _schemas():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return [None]
    rows = bind.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'transactions' ORDER BY table_schema"
        )
    ).scalars()
    return list(rows)


def upgrade():
    for schema in _schemas():
        with op.batch_alter_table("transactions", schema=schema) as batch:
            batch.alter_column("category_id", existing_type=sa.Integer(), nullable=True)


def downgrade():
    # Rows without a category block NOT NULL; leave them on the club's
    # default category, or the first one if it has none.
    bind = op.get_bind()
    for schema in _schemas():
        prefix = f'"{schema}".' if schema else ""
        bind.execute(
            sa.text(
                f"UPDATE {prefix}transactions SET category_id = ("
                f"SELECT id FROM {prefix}transaction_categories "
                "ORDER BY is_default DESC, id LIMIT 1) "
                "WHERE category_id IS NULL"
            )
        )
        with op.batch_alter_table("transactions", schema=schema) as batch:
            batch.alter_column(
                "category_id", existing_type=sa.Integer(), nullable=False
            )
