"""backup_record: global and per-club backups, club restore

There is no whole-database backup any more: a backup holds either the
public schema (``scope`` global) or one club's schema (``scope`` club, with
``tenant_id``/``tenant_slug``).  A club backup can be restored on its own;
``restored_at``, ``restore_error`` and ``safety_schema`` record the last
restore.  Existing rows were whole-database dumps and are marked
``global``.

Safe to run again per club (flask migrate-tenants): ``backup_record`` lives
only in public and each column is added once.

Revision ID: b3f1c7e9a2d4
Revises: 9e4b6d2c1a57
Create Date: 2026-10-28 16:10:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b3f1c7e9a2d4"
down_revision = "9e4b6d2c1a57"
branch_labels = None
depends_on = None

_FK = "fk_backup_record_tenant_id"


def _columns():
    return (
        sa.Column(
            "scope", sa.String(length=20), nullable=False, server_default="global"
        ),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("tenant_slug", sa.String(length=255), nullable=True),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("restore_error", sa.Text(), nullable=True),
        sa.Column("safety_schema", sa.String(length=100), nullable=True),
    )


def _public():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def upgrade():
    bind = op.get_bind()
    schema = _public()
    inspector = sa.inspect(bind)
    if not inspector.has_table("backup_record", schema=schema):
        return
    have = {c["name"] for c in inspector.get_columns("backup_record", schema=schema)}
    for column in _columns():
        if column.name not in have:
            op.add_column("backup_record", column, schema=schema)

    if bind.dialect.name == "postgresql":
        fks = {fk["name"] for fk in inspector.get_foreign_keys("backup_record", schema)}
        if _FK not in fks:
            op.create_foreign_key(
                _FK,
                "backup_record",
                "tenants",
                ["tenant_id"],
                ["id"],
                source_schema=schema,
                referent_schema=schema,
                ondelete="SET NULL",
            )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_backup_record_tenant_id "
            "ON public.backup_record (tenant_id)"
        )


def downgrade():
    bind = op.get_bind()
    schema = _public()
    inspector = sa.inspect(bind)
    if not inspector.has_table("backup_record", schema=schema):
        return
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS public.ix_backup_record_tenant_id")
        fks = {fk["name"] for fk in inspector.get_foreign_keys("backup_record", schema)}
        if _FK in fks:
            op.drop_constraint(_FK, "backup_record", schema=schema, type_="foreignkey")
    have = {c["name"] for c in inspector.get_columns("backup_record", schema=schema)}
    for column in reversed(_columns()):
        if column.name in have:
            op.drop_column("backup_record", column.name, schema=schema)
