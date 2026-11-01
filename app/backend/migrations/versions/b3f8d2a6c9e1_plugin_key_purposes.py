"""Plugin keys get a purpose: index keys and plugin keys are separate

``plugin_repositories.plugin_keys`` pins the plugin keys a repository's
index lists (JSON; empty = the old format, its index key signs plugins too).
``plugin_trusted_keys.purpose`` says what a key added by hand may sign.

Revision ID: b3f8d2a6c9e1
Revises: e7c3a9d1f5b2
Create Date: 2026-11-01 10:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b3f8d2a6c9e1"
down_revision = "e7c3a9d1f5b2"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    if "plugin_keys" not in _columns("plugin_repositories"):
        op.add_column(
            "plugin_repositories",
            sa.Column("plugin_keys", sa.Text(), nullable=False, server_default=""),
        )
    if "purpose" not in _columns("plugin_trusted_keys"):
        op.add_column(
            "plugin_trusted_keys",
            sa.Column(
                "purpose", sa.String(16), nullable=False, server_default="plugins"
            ),
        )


def downgrade():
    if "purpose" in _columns("plugin_trusted_keys"):
        op.drop_column("plugin_trusted_keys", "purpose")
    if "plugin_keys" in _columns("plugin_repositories"):
        op.drop_column("plugin_repositories", "plugin_keys")
