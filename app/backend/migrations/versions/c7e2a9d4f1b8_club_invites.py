"""Club invites: a club adds people only by a personal invite link

The table lives in public only: the person accepts on the SSO portal, with
no club selected.

Revision ID: c7e2a9d4f1b8
Revises: b4d81c2e6f9a
Create Date: 2026-10-28 21:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "c7e2a9d4f1b8"
down_revision = "b4d81c2e6f9a"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("club_invites"):
        return
    op.create_table(
        "club_invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("invited_by", sa.String(255), nullable=False, server_default=""),
        sa.Column(
            "member_data",
            postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_club_invites_email", "club_invites", ["email"])


def downgrade():
    if sa.inspect(op.get_bind()).has_table("club_invites"):
        op.drop_index("ix_club_invites_email", table_name="club_invites")
        op.drop_table("club_invites")
