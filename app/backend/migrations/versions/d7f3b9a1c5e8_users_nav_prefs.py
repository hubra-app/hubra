"""An account remembers its pinned and hidden sidebar entries

``users.nav_prefs`` is ``{"pinned": [path, ...], "hidden": [path, ...]}``.
Hidden entries move to the sidebar's "Weitere" page; pinned ones go to the top.

Revision ID: d7f3b9a1c5e8
Revises: c5e2a8d4f1b7
Create Date: 2026-10-30 23:30:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "d7f3b9a1c5e8"
down_revision = "c5e2a8d4f1b7"
branch_labels = None
depends_on = None


def upgrade():
    have = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}
    if "nav_prefs" not in have:
        op.add_column(
            "users",
            sa.Column(
                "nav_prefs",
                postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
                nullable=True,
            ),
        )


def downgrade():
    op.drop_column("users", "nav_prefs")
