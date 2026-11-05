"""Chart of accounts and fiscal years for the annual accounts

``accounts`` is the club's chart (seeded from the Swiss club chart on first
read), ``transaction_categories.account_id`` maps a category to an account,
and ``fiscal_years`` holds each year's opening and closing balances. Added
to the template tables in public and to every club schema.

Revision ID: b9e3f1a7c5d2
Revises: a8d4c2f6e1b3
Create Date: 2026-11-05 09:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "b9e3f1a7c5d2"
down_revision = "a8d4c2f6e1b3"
branch_labels = None
depends_on = None


def _schemas():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return [None]
    rows = bind.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'transaction_categories' ORDER BY table_schema"
        )
    ).scalars()
    return list(rows)


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        ref = f"{schema}." if schema else ""
        if not inspector.has_table("accounts", schema=schema):
            op.create_table(
                "accounts",
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("number", sa.String(10), nullable=False, unique=True),
                sa.Column("name", sa.String(120), nullable=False),
                sa.Column("kind", sa.String(10), nullable=False),
                sa.Column(
                    "is_money", sa.Boolean(), nullable=False, server_default=sa.false()
                ),
                schema=schema,
            )
        if not inspector.has_table("fiscal_years", schema=schema):
            op.create_table(
                "fiscal_years",
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("start", sa.Date(), nullable=False, unique=True),
                sa.Column("end", sa.Date(), nullable=False),
                sa.Column("opening", sa.JSON(), nullable=False),
                sa.Column("closing", sa.JSON(), nullable=True),
                sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column(
                    "closed_by",
                    sa.Integer(),
                    sa.ForeignKey(f"{ref}members.id", ondelete="SET NULL"),
                    nullable=True,
                ),
                schema=schema,
            )
        have = {
            c["name"]
            for c in inspector.get_columns("transaction_categories", schema=schema)
        }
        if "account_id" not in have:
            op.add_column(
                "transaction_categories",
                sa.Column(
                    "account_id",
                    sa.Integer(),
                    sa.ForeignKey(f"{ref}accounts.id", ondelete="SET NULL"),
                    nullable=True,
                ),
                schema=schema,
            )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        have = {
            c["name"]
            for c in inspector.get_columns("transaction_categories", schema=schema)
        }
        if "account_id" in have:
            op.drop_column("transaction_categories", "account_id", schema=schema)
        for table in ("fiscal_years", "accounts"):
            if inspector.has_table(table, schema=schema):
                op.drop_table(table, schema=schema)
