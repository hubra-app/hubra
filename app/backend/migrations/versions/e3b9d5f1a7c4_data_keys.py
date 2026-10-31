"""One encryption key per club for stored secrets

``data_keys``: per club (and one for the platform) a random key, stored
wrapped by the master key ``FERNET_KEY``.  Existing values stay readable
with the master key until ``flask crypto rotate`` moves them over.

Revision ID: e3b9d5f1a7c4
Revises: d1a7c3e9b5f2
Create Date: 2026-10-31 08:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e3b9d5f1a7c4"
down_revision = "d1a7c3e9b5f2"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Public only; club schemas run this too and must not get a copy.
        op.execute(
            """
            CREATE TABLE IF NOT EXISTS public.data_keys (
                id serial PRIMARY KEY,
                scope varchar(32) NOT NULL,
                version integer NOT NULL,
                wrapped_key text NOT NULL,
                created_at timestamptz NOT NULL,
                CONSTRAINT uq_data_keys_scope_version UNIQUE (scope, version)
            )
            """
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_data_keys_scope ON public.data_keys (scope)"
        )
        return
    if "data_keys" in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        "data_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope", sa.String(32), nullable=False, index=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("wrapped_key", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("scope", "version", name="uq_data_keys_scope_version"),
    )


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TABLE IF EXISTS public.data_keys")
    else:
        op.drop_table("data_keys")
