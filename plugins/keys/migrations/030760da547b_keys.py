"""keys and key_handovers

Databases that ran Hubra's own revision 2c42e69f7d52 have the tables
already; they are kept as they are.

Revision ID: 030760da547b
Revises:
Create Date: 2026-10-28 10:00:00

"""

from alembic import op
import sqlalchemy as sa

from hubra.core.plugins.ops import has_table


# revision identifiers, used by Alembic.
revision = "030760da547b"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    if has_table("keys"):
        return
    op.create_table(
        "keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("number", sa.String(length=100), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("opens", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("holder_id", sa.Integer(), nullable=True),
        sa.Column("deposit_chf", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("code_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["code_id"], ["codes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["holder_id"], ["members.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number"),
    )
    op.create_table(
        "key_handovers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=True),
        sa.Column("by_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["by_id"], ["members.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["key_id"], ["keys.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("key_handovers", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_key_handovers_key_id"), ["key_id"], unique=False
        )


def downgrade():
    # Dropping a table drops its indexes; club schemas cloned from public
    # name them differently, so they are not dropped by name.
    op.drop_table("key_handovers")
    op.drop_table("keys")
