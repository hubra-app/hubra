"""module system: manager-level allow switch, keep existing clubs' modules on

Revision ID: b1d2e3f4a5c6
Revises: f4a7c2e91b03
Create Date: 2026-10-28 09:00:00.000000

- tenant_features.allowed: the platform manager can block a module per club.
- Every module that existing clubs could reach before (all routes were open
  except mail) gets an explicit "on" row, so switching to manifest defaults
  (inventory, codes, bindings, backups and mail now start off) hides nothing
  from clubs that already use them.
- Drops the legacy feature_flag table.

Safe to run again inside a tenant schema (``flask migrate-tenants``):
public-only steps check what exists first.
"""

from alembic import op
import sqlalchemy as sa


revision = "b1d2e3f4a5c6"
down_revision = "f4a7c2e91b03"
branch_labels = None
depends_on = None

# Modules that existed before the module system: catalog name and the
# manifest default, used when the catalog row is missing (normally
# `flask seed` writes these).
_EXISTING = {
    "groups": ("Groups", True),
    "functions": ("Functions", True),
    "events": ("Events", True),
    "polls": ("Polls", True),
    "posts": ("Posts", True),
    "finance": ("Finance", True),
    "mail": ("Mail", False),
    "inventory": ("Inventory", False),
    "codes": ("Codes", False),
    "bindings": ("Bindings", False),
    "backups": ("Backups", False),
}


def _public_schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def _has_column(table, column, schema):
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table, schema=schema):
        return False
    return column in {c["name"] for c in insp.get_columns(table, schema=schema)}


def upgrade():
    schema = _public_schema()
    bind = op.get_bind()

    if not _has_column("tenant_features", "allowed", schema):
        op.add_column(
            "tenant_features",
            sa.Column("allowed", sa.Boolean(), nullable=False, server_default="1"),
            schema=schema,
        )

    if bind.dialect.name == "postgresql":
        for code, (name, default) in _EXISTING.items():
            bind.execute(
                sa.text(
                    "INSERT INTO public.features (code, name, default_enabled) "
                    "VALUES (:code, :name, :default) ON CONFLICT (code) DO NOTHING"
                ),
                {"code": code, "name": name, "default": default},
            )
            # Mail was only on where the club (or the old catalog default)
            # had it on; keep exactly that.
            enabled = (
                "COALESCE((SELECT default_enabled FROM public.features "
                "WHERE code = 'mail'), false)"
                if code == "mail"
                else "true"
            )
            bind.execute(
                sa.text(
                    "INSERT INTO public.tenant_features "
                    "(tenant_id, feature_code, enabled, allowed, created_at, updated_at) "
                    f"SELECT t.id, :code, {enabled}, true, now(), now() "
                    "FROM public.tenants t "
                    "ON CONFLICT (tenant_id, feature_code) DO NOTHING"
                ),
                {"code": code},
            )

    # Unqualified on purpose: inside a tenant run this drops the tenant's copy.
    op.execute("DROP TABLE IF EXISTS feature_flag")


def downgrade():
    schema = _public_schema()
    op.create_table(
        "feature_flag",
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )
    if _has_column("tenant_features", "allowed", schema):
        op.drop_column("tenant_features", "allowed", schema=schema)
