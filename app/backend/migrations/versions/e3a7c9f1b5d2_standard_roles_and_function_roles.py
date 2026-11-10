"""Standard roles: role and function keys, functions give several roles

* ``roles.key`` and ``functions.key``: stable names of the standard roles and
  functions (``member``, ``board``, ``treasurer`` …), so plugins and upgrades
  find them whatever a club renamed them to.
* ``function_roles``: a function gives several roles (Kassier/in gives
  Vorstand and Treasurer). The old single ``grants_tenant_role_id`` is copied
  in and no longer read.
* The system roles that already exist get their key.

Added to the template tables in public and to every club schema. The
standard roles, functions and module access themselves are added by
``flask roles standardise`` (part of ``flask seed``), docs/roles.md.

Revision ID: e3a7c9f1b5d2
Revises: 8395bc432cbb
Create Date: 2026-11-09 15:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e3a7c9f1b5d2"
down_revision = "8395bc432cbb"
branch_labels = None
depends_on = None

SYSTEM_KEYS = {"Owner": "owner", "Admin": "admin", "Treasurer": "treasurer", "Member": "member"}


def _schemas():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return [None]
    rows = bind.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'functions' ORDER BY table_schema"
        )
    ).scalars()
    return list(rows)


def _q(schema, table):
    return f'"{schema}"."{table}"' if schema else table


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for schema in _schemas():
        ref = f"{schema}." if schema else ""
        for table in ("roles", "functions"):
            cols = {c["name"] for c in inspector.get_columns(table, schema=schema)}
            if "key" not in cols:
                op.add_column(
                    table, sa.Column("key", sa.String(50), nullable=True), schema=schema
                )
                op.create_index(
                    f"ix_{table}_key", table, ["key"], unique=True, schema=schema
                )
        if not inspector.has_table("function_roles", schema=schema):
            op.create_table(
                "function_roles",
                sa.Column(
                    "function_id",
                    sa.Integer(),
                    sa.ForeignKey(f"{ref}functions.id", ondelete="CASCADE"),
                    primary_key=True,
                ),
                sa.Column(
                    "role_id",
                    sa.Integer(),
                    sa.ForeignKey(f"{ref}roles.id", ondelete="CASCADE"),
                    primary_key=True,
                ),
                schema=schema,
            )
            op.create_index(
                "ix_function_roles_role_id", "function_roles", ["role_id"], schema=schema
            )
            bind.execute(
                sa.text(
                    f"INSERT INTO {_q(schema, 'function_roles')} (function_id, role_id) "
                    f"SELECT id, grants_tenant_role_id FROM {_q(schema, 'functions')} "
                    "WHERE grants_tenant_role_id IS NOT NULL"
                )
            )
        for name, key in SYSTEM_KEYS.items():
            bind.execute(
                sa.text(
                    f"UPDATE {_q(schema, 'roles')} SET key = :key "
                    "WHERE name = :name AND is_system AND key IS NULL "
                    f"AND NOT EXISTS (SELECT 1 FROM {_q(schema, 'roles')} r2 WHERE r2.key = :key)"
                ),
                {"key": key, "name": name},
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for schema in _schemas():
        if inspector.has_table("function_roles", schema=schema):
            op.drop_table("function_roles", schema=schema)
        for table in ("roles", "functions"):
            cols = {c["name"] for c in inspector.get_columns(table, schema=schema)}
            if "key" in cols:
                op.drop_index(f"ix_{table}_key", table_name=table, schema=schema)
                op.drop_column(table, "key", schema=schema)
