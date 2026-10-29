"""Members may sign up for events

The system role Member could read events but had no right to sign up
(``events.events.register``), and system roles cannot be edited, so in no
club could an ordinary member join an event. New clubs get it from
``_seed_tenant``; this gives it to the Member role of every existing club.

Safe to run again: the role only gets the permission if it lacks it.

Revision ID: f3c8e1a7b5d2
Revises: d1a6e4b8c3f2
Create Date: 2026-10-29 01:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f3c8e1a7b5d2"
down_revision = "d1a6e4b8c3f2"
branch_labels = None
depends_on = None

_KEY = "events.events.register"


def _club_schemas():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return []
    rows = bind.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'role_permissions' AND table_schema <> 'public' "
            "ORDER BY table_schema"
        )
    ).scalars()
    return list(rows)


def upgrade():
    bind = op.get_bind()
    for schema in _club_schemas():
        bind.execute(
            sa.text(
                f"INSERT INTO {schema}.role_permissions (role_id, permission_id) "
                f"SELECT r.id, p.id FROM {schema}.roles r "
                "JOIN public.permissions p ON p.key = :key "
                "WHERE r.name = 'Member' AND r.is_system AND NOT EXISTS "
                f"(SELECT 1 FROM {schema}.role_permissions x "
                "WHERE x.role_id = r.id AND x.permission_id = p.id)"
            ),
            {"key": _KEY},
        )


def downgrade():
    bind = op.get_bind()
    for schema in _club_schemas():
        bind.execute(
            sa.text(
                f"DELETE FROM {schema}.role_permissions rp "
                f"USING {schema}.roles r, public.permissions p "
                "WHERE rp.role_id = r.id AND rp.permission_id = p.id "
                "AND r.name = 'Member' AND r.is_system AND p.key = :key"
            ),
            {"key": _KEY},
        )
