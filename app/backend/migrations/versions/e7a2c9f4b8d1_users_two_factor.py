"""Two-factor sign-in with an authenticator app (TOTP) and recovery codes

The secret is Fernet-encrypted; recovery codes are SHA-256 hashes.

Revision ID: e7a2c9f4b8d1
Revises: d3f8b1a6c2e9
Create Date: 2026-10-31 08:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "e7a2c9f4b8d1"
down_revision = "d3f8b1a6c2e9"
branch_labels = None
depends_on = None

_JSON = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")

_COLUMNS = [
    sa.Column("totp_secret", sa.Text(), nullable=True),
    sa.Column("totp_pending_secret", sa.Text(), nullable=True),
    sa.Column("totp_enabled_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("totp_last_step", sa.Integer(), nullable=True),
    sa.Column("recovery_codes", _JSON, nullable=True),
]


def upgrade():
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}
    for column in _COLUMNS:
        if column.name not in have:
            op.add_column("users", column)


def downgrade():
    for column in reversed(_COLUMNS):
        op.drop_column("users", column.name)
