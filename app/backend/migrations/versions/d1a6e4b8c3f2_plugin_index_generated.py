"""Remember the newest plugin index seen per repository

``plugin_repositories.index_generated`` holds the ``generated`` time of the
newest signed index fetched; an older one is refused (rollback protection).

Revision ID: d1a6e4b8c3f2
Revises: c7e2a9d4f1b8
Create Date: 2026-10-28 21:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d1a6e4b8c3f2"
down_revision = "c7e2a9d4f1b8"
branch_labels = None
depends_on = None


def upgrade():
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("plugin_repositories")}
    if "index_generated" not in have:
        op.add_column(
            "plugin_repositories",
            sa.Column(
                "index_generated", sa.String(40), nullable=False, server_default=""
            ),
        )


def downgrade():
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("plugin_repositories")}
    if "index_generated" in have:
        op.drop_column("plugin_repositories", "index_generated")
