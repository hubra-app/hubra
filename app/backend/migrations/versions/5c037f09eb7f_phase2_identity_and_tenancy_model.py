"""phase2_identity_and_tenancy_model

Revision ID: 5c037f09eb7f
Revises: 28a0702d778a
Create Date: 2026-07-13 13:39:05.583393

Phase 2: Extend identity & tenancy models for multi-tenant SaaS.

All changes are additive — no columns dropped, no breaking changes.
Public schema: user_tenants, tenant_requests, tenants
Per-tenant schema template: roles, functions, function_holders
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "5c037f09eb7f"
down_revision = "28a0702d778a"
branch_labels = None
depends_on = None


def upgrade():
    # ── Public schema: user_tenants ──────────────────────────────────────
    with op.batch_alter_table("user_tenants", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "status", sa.String(length=20), server_default="active", nullable=False
            )
        )
        batch_op.add_column(
            sa.Column(
                "is_owner",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            )
        )

    # ── Public schema: tenant_requests ───────────────────────────────────
    with op.batch_alter_table("tenant_requests", schema=None) as batch_op:
        batch_op.add_column(sa.Column("purpose", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("rejection_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("created_tenant_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_tenant_requests_reviewed_by_users",
            "users",
            ["reviewed_by"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_tenant_requests_created_tenant_id_tenants",
            "tenants",
            ["created_tenant_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # ── Public schema: tenants ───────────────────────────────────────────
    with op.batch_alter_table("tenants", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "locale", sa.String(length=10), server_default="de-CH", nullable=False
            )
        )
        batch_op.add_column(
            sa.Column(
                "timezone",
                sa.String(length=50),
                server_default="Europe/Zurich",
                nullable=False,
            )
        )

    # ── Per-tenant schema template: roles ────────────────────────────────
    with op.batch_alter_table("roles", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_system",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "is_owner",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            )
        )

    # ── Per-tenant schema template: functions ────────────────────────────
    with op.batch_alter_table("functions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("grants_tenant_role_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("mailbox_ref", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "is_singleton",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            )
        )
        batch_op.create_foreign_key(
            "fk_functions_grants_tenant_role_id_roles",
            "roles",
            ["grants_tenant_role_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # ── Per-tenant schema template: function_holders ─────────────────────
    with op.batch_alter_table("function_holders", schema=None) as batch_op:
        batch_op.add_column(sa.Column("term_start", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("term_end", sa.Date(), nullable=True))


def downgrade():
    with op.batch_alter_table("function_holders", schema=None) as batch_op:
        batch_op.drop_column("term_end")
        batch_op.drop_column("term_start")

    with op.batch_alter_table("functions", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_functions_grants_tenant_role_id_roles", type_="foreignkey"
        )
        batch_op.drop_column("is_singleton")
        batch_op.drop_column("mailbox_ref")
        batch_op.drop_column("grants_tenant_role_id")

    with op.batch_alter_table("roles", schema=None) as batch_op:
        batch_op.drop_column("is_owner")
        batch_op.drop_column("is_system")

    with op.batch_alter_table("tenants", schema=None) as batch_op:
        batch_op.drop_column("timezone")
        batch_op.drop_column("locale")

    with op.batch_alter_table("tenant_requests", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_tenant_requests_created_tenant_id_tenants", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_tenant_requests_reviewed_by_users", type_="foreignkey"
        )
        batch_op.drop_column("created_tenant_id")
        batch_op.drop_column("rejection_reason")
        batch_op.drop_column("purpose")

    with op.batch_alter_table("user_tenants", schema=None) as batch_op:
        batch_op.drop_column("updated_at")
        batch_op.drop_column("is_owner")
        batch_op.drop_column("status")
