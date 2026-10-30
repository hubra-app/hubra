"""An account remembers its light, dark or system appearance

``users.theme`` is ``light``, ``dark`` or ``auto`` (follow the browser).
Sign-in hands it to every portal as the ``hubra_theme`` cookie.

Revision ID: c5e2a8d4f1b7
Revises: b3d7f1a9c2e4
Create Date: 2026-10-30 19:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c5e2a8d4f1b7"
down_revision = "b3d7f1a9c2e4"
branch_labels = None
depends_on = None


def upgrade():
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}
    if "theme" not in have:
        op.add_column(
            "users",
            sa.Column("theme", sa.String(10), nullable=False, server_default="auto"),
        )


def downgrade():
    op.drop_column("users", "theme")
