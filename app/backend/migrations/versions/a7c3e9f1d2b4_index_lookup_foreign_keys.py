"""Index the foreign keys that lists and permission checks look up by

Postgres does not index foreign keys, so "members of this tier" or "roles
of this member" scanned whole club tables. The indexes are added to the
public template tables (new clubs copy them) and to every club schema.

Revision ID: a7c3e9f1d2b4
Revises: d1a6e4b8c3f2
Create Date: 2026-10-28 23:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a7c3e9f1d2b4"
down_revision = "d1a6e4b8c3f2"
branch_labels = None
depends_on = None

# Kept in step with hubra/core/models/indexes.py (copied, so this migration
# keeps working when that list changes).
INDEXES = (
    ("members", "user_id"),
    ("members", "tier_id"),
    ("member_roles", "role_id"),
    ("member_groups", "group_id"),
    ("group_memberships", "member_id"),
    ("invoices", "member_id"),
    ("transactions", "member_id"),
    ("event_attendees", "member_id"),
    ("event_registrations", "member_id"),
    ("notifications", "member_id"),
    ("post_comments", "post_id"),
    ("poll_options", "poll_id"),
    ("poll_votes", "member_id"),
    ("poll_votes", "option_id"),
    ("inventory_checkouts", "item_id"),
    ("user_tenants", "tenant_id"),
)


def _schemas_with(table: str) -> list[str | None]:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return [None] if sa.inspect(bind).has_table(table) else []
    return list(
        bind.execute(
            sa.text(
                "SELECT table_schema FROM information_schema.tables "
                "WHERE table_name = :t ORDER BY table_schema"
            ),
            {"t": table},
        ).scalars()
    )


def _has_index_on(inspector, table: str, column: str, schema) -> bool:
    """True when some index already leads with the column (a club schema
    cloned after the model change has it under a generated name)."""
    for ix in inspector.get_indexes(table, schema=schema):
        if ix["column_names"] and ix["column_names"][0] == column:
            return True
    return False


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for table, column in INDEXES:
        for schema in _schemas_with(table):
            if not _has_index_on(inspector, table, column, schema):
                op.create_index(f"ix_{table}_{column}", table, [column], schema=schema)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for table, column in INDEXES:
        name = f"ix_{table}_{column}"
        for schema in _schemas_with(table):
            if any(ix["name"] == name for ix in inspector.get_indexes(table, schema=schema)):
                op.drop_index(name, table_name=table, schema=schema)
