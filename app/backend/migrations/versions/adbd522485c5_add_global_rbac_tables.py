"""add global rbac tables

Revision ID: adbd522485c5
Revises: a029a5f02fd3
Create Date: 2026-07-12 15:40:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "adbd522485c5"
down_revision = "a029a5f02fd3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "global_permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=255), unique=True, nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
    )

    op.create_table(
        "global_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), unique=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )

    op.create_table(
        "global_role_permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "role_id",
            sa.Integer(),
            sa.ForeignKey("global_roles.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "permission_id",
            sa.Integer(),
            sa.ForeignKey("global_permissions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.UniqueConstraint("role_id", "permission_id"),
    )

    op.create_table(
        "user_global_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "role_id",
            sa.Integer(),
            sa.ForeignKey("global_roles.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.UniqueConstraint("user_id", "role_id"),
    )


def downgrade():
    op.drop_table("user_global_roles")
    op.drop_table("global_role_permissions")
    op.drop_table("global_roles")
    op.drop_table("global_permissions")
