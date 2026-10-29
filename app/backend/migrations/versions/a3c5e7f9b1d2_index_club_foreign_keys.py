"""Index the club tables' foreign keys that lists and lookups filter on

Postgres does not index foreign keys by itself, so finding a member by
account (every sign-in and ``/account``), the members of a tier, group or
role, and a member's invoices and notifications read the whole table.
The indexes go on the template tables in public and on every club schema;
new clubs copy them with ``LIKE ... INCLUDING ALL``.

Revision ID: a3c5e7f9b1d2
Revises: d1a6e4b8c3f2
Create Date: 2026-10-28 23:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a3c5e7f9b1d2"
down_revision = "d1a6e4b8c3f2"
branch_labels = None
depends_on = None


# (table, column); the index is ix_<table>_<column>, as index=True names it.
INDEXES = [
    ("members", "user_id"),
    ("members", "tier_id"),
    ("member_groups", "group_id"),
    ("member_roles", "role_id"),
    ("invoices", "member_id"),
    ("notifications", "member_id"),
]


def _schemas():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return [None]
    rows = bind.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'members' ORDER BY table_schema"
        )
    ).scalars()
    return list(rows)


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        for table, column in INDEXES:
            if not inspector.has_table(table, schema=schema):
                continue
            op.create_index(
                f"ix_{table}_{column}",
                table,
                [column],
                schema=schema,
                if_not_exists=True,
            )


def downgrade():
    for schema in _schemas():
        for table, column in INDEXES:
            op.drop_index(
                f"ix_{table}_{column}", table_name=table, schema=schema, if_exists=True
            )
