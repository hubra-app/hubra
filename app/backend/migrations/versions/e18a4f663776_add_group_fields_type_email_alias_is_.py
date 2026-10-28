"""add group fields type email_alias is_public parent_group_id deleted_at and group_memberships table

Revision ID: e18a4f663776
Revises: 5ad9717c8742
Create Date: 2026-07-10 13:58:56.275063

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "e18a4f663776"
down_revision = "5ad9717c8742"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("groups", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "type",
                sa.String(length=50),
                nullable=False,
                server_default="interest_group",
            )
        )
        batch_op.add_column(
            sa.Column("email_alias", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "is_public",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            )
        )
        batch_op.add_column(sa.Column("parent_group_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_groups_parent_group_id",
            "groups",
            ["parent_group_id"],
            ["id"],
        )

    op.create_table(
        "group_memberships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column(
            "role", sa.String(length=50), nullable=False, server_default="member"
        ),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "member_id", name="uq_group_member"),
    )


def downgrade():
    op.drop_table("group_memberships")

    with op.batch_alter_table("groups", schema=None) as batch_op:
        batch_op.drop_constraint("fk_groups_parent_group_id", type_="foreignkey")
        batch_op.drop_column("deleted_at")
        batch_op.drop_column("parent_group_id")
        batch_op.drop_column("is_public")
        batch_op.drop_column("email_alias")
        batch_op.drop_column("type")
