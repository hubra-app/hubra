"""user_tenants: link every club member's account to the club

Members added inside a club (Members → Add, CSV import, approved
applications) never got a public.user_tenants row, so sign-in skipped
the club and switch-tenant refused it. New members get the link now; this
adds it for the ones made before. Uses schema-qualified names and
ON CONFLICT, so running it again per club (flask migrate-tenants) is a no-op.

Revision ID: 3e7a9c1d5b20
Revises: 202ee240e1d8
Create Date: 2026-10-28 13:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3e7a9c1d5b20"
down_revision = "202ee240e1d8"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    inspector = sa.inspect(bind)
    tenant_ids = bind.execute(
        sa.text("SELECT id FROM public.tenants WHERE deleted_at IS NULL")
    ).scalars()
    for tenant_id in tenant_ids:
        schema = f"tenant_{int(tenant_id)}"
        if not inspector.has_table("members", schema=schema):
            continue
        bind.execute(
            sa.text(
                "INSERT INTO public.user_tenants"
                " (user_id, tenant_id, status, is_owner, created_at, updated_at)"
                " SELECT DISTINCT m.user_id, :tenant_id, 'active', false, now(), now()"
                f" FROM {schema}.members m"
                " WHERE m.user_id IS NOT NULL AND m.archived_at IS NULL"
                " ON CONFLICT ON CONSTRAINT uq_user_tenant DO NOTHING"
            ),
            {"tenant_id": int(tenant_id)},
        )


def downgrade():
    # The links are correct data; nothing to undo.
    pass
