"""Club roles use the permission catalog in public

Every club schema got its own, empty copy of ``permissions`` because the
roles module listed the table as a club table.  Inside a club the empty copy
hid the real catalog in public, so new clubs were seeded without any role
permissions: ordinary members got 403 on events, posts, polls and groups, and
custom roles could not be given permissions.

For each club schema that has the copy:

* role permissions that point at the copy are moved to the public row with
  the same key (rows without a match are dropped),
* the copy is dropped,
* the system roles Member and Treasurer get their default permissions if
  they have none (system roles cannot be edited, so empty means broken).

Safe to run again: a second run finds no club ``permissions`` table.

Revision ID: d7e2a9c4b6f1
Revises: b3f1c7e9a2d4
Create Date: 2026-10-28 16:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d7e2a9c4b6f1"
down_revision = "b3f1c7e9a2d4"
branch_labels = None
depends_on = None

# The defaults _seed_tenant gives new clubs, as of this revision.
_DEFAULTS = {
    "Treasurer": (
        "finance.transactions.read",
        "finance.transactions.create",
        "finance.transactions.update",
        "finance.transactions.delete",
        "finance.invoices.read",
        "finance.invoices.create",
        "finance.invoices.update",
        "finance.invoices.delete",
        "finance.invoices.remind",
        "finance.invoices.read_reminders",
        "finance.overview.read",
        "finance.transaction_categories.read",
        "finance.transaction_categories.create",
        "finance.transaction_categories.update",
        "finance.transaction_categories.delete",
        "finance.external_parties.read",
        "finance.external_parties.create",
        "finance.external_parties.update",
        "finance.external_parties.delete",
        "members.members.read",
        "tiers.tiers.read",
        "tiers.tiers.calculate_cost",
        "tiers.tiers.read_members",
        "audit.audit.read",
        "dashboard.dashboard.read",
    ),
    "Member": (
        "members.members.read",
        "groups.groups.read",
        "events.events.read",
        "polls.polls.read",
        "polls.polls.vote",
        "posts.posts.read",
        "posts.posts.like",
        "posts.posts.comment",
        "dashboard.dashboard.read",
        "notifications.notifications.read",
    ),
}


def _club_schemas_with(table):
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return []
    rows = bind.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = :t AND table_schema <> 'public' "
            "ORDER BY table_schema"
        ),
        {"t": table},
    ).scalars()
    return list(rows)


def upgrade():
    bind = op.get_bind()
    for schema in _club_schemas_with("permissions"):
        bind.execute(
            sa.text(
                f"UPDATE {schema}.role_permissions rp SET permission_id = pub.id "
                f"FROM {schema}.permissions own "
                "JOIN public.permissions pub ON pub.key = own.key "
                "WHERE rp.permission_id = own.id"
            )
        )
        bind.execute(
            sa.text(
                f"DELETE FROM {schema}.role_permissions rp "
                "WHERE rp.permission_id IS NOT NULL AND NOT EXISTS "
                "(SELECT 1 FROM public.permissions p WHERE p.id = rp.permission_id)"
            )
        )
        op.execute(f"DROP TABLE {schema}.permissions")

        for role, keys in _DEFAULTS.items():
            bind.execute(
                sa.text(
                    f"INSERT INTO {schema}.role_permissions (role_id, permission_id) "
                    f"SELECT r.id, p.id FROM {schema}.roles r "
                    "JOIN public.permissions p ON p.key = ANY(:keys) "
                    "WHERE r.name = :role AND r.is_system AND NOT EXISTS "
                    f"(SELECT 1 FROM {schema}.role_permissions x WHERE x.role_id = r.id)"
                ),
                {"role": role, "keys": list(keys)},
            )


def downgrade():
    # The club copies were empty by mistake; nothing to restore.
    pass
