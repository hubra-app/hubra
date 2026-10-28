"""Indexes on foreign keys that lists and permission checks look up by.

Postgres indexes primary keys and unique constraints, not foreign keys, so
"members of this tier", "roles of this member's account" or "invoices of
this member" scanned the whole club table. Club schemas copy their indexes
from the public template tables (``LIKE ... INCLUDING ALL``), so declaring
them here covers new clubs; migration a7c3e9f1d2b4 adds them to existing
ones.
"""

from sqlalchemy import Index

from hubra.core.extensions import db

LOOKUP_INDEXES: tuple[tuple[str, str], ...] = (
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


def index_name(table: str, column: str) -> str:
    return f"ix_{table}_{column}"


for _table, _column in LOOKUP_INDEXES:
    Index(index_name(_table, _column), db.metadata.tables[_table].c[_column])
