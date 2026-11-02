"""platform_plans + platform_addons: plans and paid add-ons with list
prices, set in manage; the plan limits move here from platform settings

The three plans Hubra had (starter, growth, enterprise) become rows, with
the limits and prices set so far (platform settings ``limits.<plan>.*`` and
``billing.price.<plan>``, which are removed).  Public-schema only, so the
revision is safe to run again per club (flask migrate-tenants).

Revision ID: b6e2f8a4c0d9
Revises: e5c1a7d3b9f4
Create Date: 2026-11-02 16:00:00.000000

"""

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "b6e2f8a4c0d9"
down_revision = "e5c1a7d3b9f4"
branch_labels = None
depends_on = None

_PLANS = (
    ("starter", "Starter", 1),
    ("growth", "Growth", 2),
    ("enterprise", "Enterprise", 3),
)
_KINDS = ("members", "mail_month", "storage_mb")


def _public_schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def _setting(bind, schema, key):
    table = f"{schema}.platform_settings" if schema else "platform_settings"
    try:
        return bind.execute(
            sa.text(f"SELECT value FROM {table} WHERE key = :k"), {"k": key}
        ).scalar()
    except Exception:  # noqa: BLE001  (no settings table yet)
        return None


def upgrade():
    schema = _public_schema()
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    json = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")
    if not inspector.has_table("platform_plans", schema=schema):
        plans = op.create_table(
            "platform_plans",
            sa.Column("key", sa.String(40), nullable=False),
            sa.Column("name_de", sa.String(80), nullable=False),
            sa.Column("name_en", sa.String(80), nullable=False),
            sa.Column("description_de", sa.Text(), nullable=False),
            sa.Column("description_en", sa.Text(), nullable=False),
            sa.Column("price_month_chf", sa.Numeric(10, 2), nullable=True),
            sa.Column("price_year_chf", sa.Numeric(10, 2), nullable=True),
            sa.Column("features", json, nullable=True),
            sa.Column("limit_members", sa.Integer(), nullable=True),
            sa.Column("limit_mail_month", sa.Integer(), nullable=True),
            sa.Column("limit_storage_mb", sa.Integer(), nullable=True),
            sa.Column("public", sa.Boolean(), nullable=False),
            sa.Column("highlighted", sa.Boolean(), nullable=False),
            sa.Column("sort", sa.Integer(), nullable=False),
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("key"),
            schema=schema,
        )
        rows = []
        for key, name, sort in _PLANS:
            limits = {}
            for kind in _KINDS:
                raw = str(_setting(bind, schema, f"limits.{key}.{kind}") or "").strip()
                limits[f"limit_{kind}"] = int(raw) if raw.isdigit() else None
            price = str(_setting(bind, schema, f"billing.price.{key}") or "").strip()
            rows.append(
                {
                    "key": key,
                    "name_de": name,
                    "name_en": name,
                    "description_de": "",
                    "description_en": "",
                    "price_month_chf": price or None,
                    "price_year_chf": None,
                    "features": [],
                    **limits,
                    "public": False,
                    "highlighted": False,
                    "sort": sort,
                    "archived_at": None,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
        op.bulk_insert(plans, rows)
        table = f"{schema}.platform_settings" if schema else "platform_settings"
        if inspector.has_table("platform_settings", schema=schema):
            bind.execute(
                sa.text(
                    f"DELETE FROM {table} WHERE key LIKE 'billing.price.%' "
                    "OR (key LIKE 'limits.%.%' AND key <> 'limits.warn_percent')"
                )
            )
    if not inspector.has_table("platform_addons", schema=schema):
        op.create_table(
            "platform_addons",
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("price_month_chf", sa.Numeric(10, 2), nullable=True),
            sa.Column("public", sa.Boolean(), nullable=False),
            sa.Column("label_de", sa.String(120), nullable=False),
            sa.Column("label_en", sa.String(120), nullable=False),
            sa.Column("note_de", sa.Text(), nullable=False),
            sa.Column("note_en", sa.Text(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("code"),
            schema=schema,
        )


def downgrade():
    schema = _public_schema()
    op.drop_table("platform_addons", schema=schema)
    op.drop_table("platform_plans", schema=schema)
