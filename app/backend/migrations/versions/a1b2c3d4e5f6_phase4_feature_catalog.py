"""phase4_feature_catalog

Revision ID: a1b2c3d4e5f6
Revises: 5c037f09eb7f
Create Date: 2026-07-13 15:37:00.000000

Phase 4: Feature catalog and per-tenant feature grants.

Creates two new tables in the public schema:
- features: catalog of all available features (code, name, default_enabled)
- tenant_features: per-tenant grants overriding catalog defaults

The old per-tenant feature_flag table is kept for backward compatibility.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "5c037f09eb7f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "features",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "default_enabled",
            sa.Boolean(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("code"),
    )

    op.create_table(
        "tenant_features",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "feature_code",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default="1",
            nullable=False,
        ),
        sa.Column(
            "config",
            postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["feature_code"], ["features.code"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("tenant_id", "feature_code", name="uq_tenant_feature"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tenant_features_tenant_id",
        "tenant_features",
        ["tenant_id"],
    )
    op.create_index(
        "ix_tenant_features_feature_code",
        "tenant_features",
        ["feature_code"],
    )


def downgrade():
    op.drop_index("ix_tenant_features_feature_code", table_name="tenant_features")
    op.drop_index("ix_tenant_features_tenant_id", table_name="tenant_features")
    op.drop_table("tenant_features")
    op.drop_table("features")
