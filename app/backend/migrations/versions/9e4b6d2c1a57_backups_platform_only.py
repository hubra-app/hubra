"""Backups are platform-only: records move to public, the club module goes

A backup dumps the whole database, so starting, verifying or deleting one
is for platform staff (global permission ``backups.manage``), not for a
club's admins.  ``backup_record`` lives once in public: rows kept in club
schemas are copied there (their S3 objects stay where they are) and the club
tables are dropped.  The ``backups`` club module is removed from the
catalog and from every club.

Safe to run again per club (flask migrate-tenants): club tables are found
and handled in one go, a second run finds none.

Revision ID: 9e4b6d2c1a57
Revises: 5c8e2a4f7d31
Create Date: 2026-10-28 15:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9e4b6d2c1a57"
down_revision = "5c8e2a4f7d31"
branch_labels = None
depends_on = None

_COLUMNS = (
    "created_at, type, status, size_bytes, s3_key, checksum, verified_at, "
    "verified_ok, verify_error, error_message, triggered_by, table_count"
)


def _club_schemas_with(table):
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return []
    rows = bind.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = :t AND table_schema <> 'public' "
            "ORDER BY table_schema"
        ),
        {"t": table},
    ).scalars()
    return list(rows)


def upgrade():
    bind = op.get_bind()
    public = "public" if bind.dialect.name == "postgresql" else None
    if not sa.inspect(bind).has_table("backup_record", schema=public):
        op.create_table(
            "backup_record",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("type", sa.String(length=30), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("size_bytes", sa.BigInteger(), nullable=True),
            sa.Column("s3_key", sa.String(length=500), nullable=True),
            sa.Column("checksum", sa.String(length=64), nullable=True),
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("verified_ok", sa.Boolean(), nullable=True),
            sa.Column("verify_error", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("triggered_by", sa.String(length=255), nullable=True),
            sa.Column("table_count", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            schema=public,
        )
    for schema in _club_schemas_with("backup_record"):
        bind.execute(
            sa.text(
                f"INSERT INTO public.backup_record ({_COLUMNS}) "
                f'SELECT {_COLUMNS} FROM "{schema}".backup_record'
            )
        )
        op.drop_table("backup_record", schema=schema)

    inspector = sa.inspect(bind)
    if inspector.has_table("tenant_features", schema=public):
        tf = sa.table("tenant_features", sa.column("feature_code"), schema=public)
        bind.execute(tf.delete().where(tf.c.feature_code == "backups"))
    if inspector.has_table("features", schema=public):
        f = sa.table("features", sa.column("code"), schema=public)
        bind.execute(f.delete().where(f.c.code == "backups"))


def downgrade():
    # The records stay in public; the module comes back with its code.
    pass
