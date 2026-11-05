"""Platform role assignments limited to some clubs

Public schema. A row in ``user_global_role_tenants`` limits one role
assignment (``user_global_roles``) to that club; an assignment without rows
holds on the whole platform, as before.

Revision ID: a8d4c2f6e1b3
Revises: c6f1a8d3e2b7
Create Date: 2026-11-05 08:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "a8d4c2f6e1b3"
down_revision = "c6f1a8d3e2b7"
branch_labels = None
depends_on = None


def upgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "user_global_role_tenants" in tables:
        return
    op.create_table(
        "user_global_role_tenants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "assignment_id",
            sa.Integer(),
            sa.ForeignKey("user_global_roles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("assignment_id", "tenant_id"),
    )
    op.create_index(
        "ix_user_global_role_tenants_assignment_id",
        "user_global_role_tenants",
        ["assignment_id"],
    )
    op.create_index(
        "ix_user_global_role_tenants_tenant_id",
        "user_global_role_tenants",
        ["tenant_id"],
    )


def downgrade():
    op.drop_table("user_global_role_tenants")
