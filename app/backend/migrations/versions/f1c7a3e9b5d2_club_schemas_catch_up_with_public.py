"""Club schemas catch up with public

``0ac79fcc9933`` (recurring transactions) and ``ee771f92971b`` (invoice
periods) changed only the template tables in public.  Clubs created before
them have no ``transactions.recurring_id``, ``invoices.period_start`` /
``period_end`` or ``recurring_transactions`` table, so their finance pages
fail with ``UndefinedColumn``.  This adds every table and column public has
and a club schema lacks (``hubra.core.tenant.schema_sync``); the init step
does the same on every start from now on.

Revision ID: f1c7a3e9b5d2
Revises: b4e8f2a6d9c3
Create Date: 2026-11-05 00:30:00.000000

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "f1c7a3e9b5d2"
down_revision = "b4e8f2a6d9c3"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    from hubra.core.tenant.schema_manager import tables_to_clone
    from hubra.core.tenant.schema_sync import catch_up_all

    for result in catch_up_all(bind, tables_to_clone()):
        for table, rows in result.rows_in_public.items():
            print(
                f"  {result.schema}.{table} was missing; public.{table} has "
                f"{rows} row(s) a club may have written there (not moved)"
            )


def downgrade():
    # Only adds what the earlier migrations should have added; their own
    # downgrades remove it again.
    pass
