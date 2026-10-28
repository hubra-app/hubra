"""Drop the per-club SMTP and backup storage settings

The outbound relay and the backup storage are platform settings now
(``platform_settings``: ``mail.relay.*`` and ``backup.s3.*``, defaulting to
env).  The old copies in every club's ``setting`` table were seeded from the
same env vars and no longer read, so they go.  A value someone typed into a
club's settings screen instead of env is not carried over; set it again
under Platform settings in manage.

Safe to run again per club (flask migrate-tenants): every schema is cleaned
in one go and a second run finds nothing.

Revision ID: 5c8e2a4f7d31
Revises: 7b2d4f6a8c10
Create Date: 2026-10-28 15:10:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5c8e2a4f7d31"
down_revision = "7b2d4f6a8c10"
branch_labels = None
depends_on = None

_KEYS = (
    "mail.smtp_host",
    "mail.smtp_port",
    "mail.smtp_user",
    "mail.smtp_password",
    "backup.s3_endpoint",
    "backup.s3_bucket",
    "backup.s3_access_key",
    "backup.s3_secret_key",
    "backup.s3_region",
)


def _schemas_with(table):
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return [None] if sa.inspect(bind).has_table(table) else []
    rows = bind.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = :t ORDER BY table_schema"
        ),
        {"t": table},
    ).scalars()
    return list(rows)


def upgrade():
    bind = op.get_bind()
    for schema in _schemas_with("setting"):
        table = sa.table("setting", sa.column("key"), schema=schema)
        bind.execute(table.delete().where(table.c.key.in_(_KEYS)))


def downgrade():
    # Club provisioning no longer seeds these; nothing reads them either.
    pass
