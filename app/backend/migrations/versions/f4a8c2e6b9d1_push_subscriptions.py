"""Browser push subscriptions

``push_subscriptions``: one row per browser (device) that gets a person's
notifications as pushes, in the public schema (per account, every club).

Revision ID: f4a8c2e6b9d1
Revises: e7c3a9d1f5b2
Create Date: 2026-11-01 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f4a8c2e6b9d1"
down_revision = "e7c3a9d1f5b2"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("push_subscriptions"):
        return
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.Text(), nullable=False, unique=True),
        sa.Column("p256dh", sa.String(255), nullable=False),
        sa.Column("auth", sa.String(255), nullable=False),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"]
    )


def downgrade():
    if sa.inspect(op.get_bind()).has_table("push_subscriptions"):
        op.drop_index("ix_push_subscriptions_user_id", "push_subscriptions")
        op.drop_table("push_subscriptions")
