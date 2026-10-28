"""add event fields and event_registrations table

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-07-10 15:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b3c4d5e6f7a8"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("club_events", schema=None) as batch_op:
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("meeting_url", sa.String(length=500), nullable=True)
        )
        batch_op.add_column(sa.Column("end_date", sa.Date(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "all_day", sa.Boolean(), nullable=False, server_default=sa.text("false")
            )
        )
        batch_op.add_column(
            sa.Column(
                "category",
                sa.String(length=50),
                nullable=False,
                server_default="general",
            )
        )
        batch_op.add_column(sa.Column("max_attendees", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "registration_deadline", sa.DateTime(timezone=True), nullable=True
            )
        )
        batch_op.add_column(
            sa.Column(
                "cancellation_deadline", sa.DateTime(timezone=True), nullable=True
            )
        )
        batch_op.add_column(
            sa.Column(
                "requires_approval",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "is_public",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )
        batch_op.add_column(
            sa.Column("cover_image_url", sa.String(length=500), nullable=True)
        )
        batch_op.add_column(sa.Column("color", sa.String(length=7), nullable=True))
        batch_op.add_column(sa.Column("created_by", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_club_events_created_by",
            "members",
            ["created_by"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_table(
        "event_registrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.String(length=50), nullable=False, server_default="registered"
        ),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("guests", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["event_id"], ["club_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "member_id", name="uq_event_registration"),
    )


def downgrade():
    op.drop_table("event_registrations")

    with op.batch_alter_table("club_events", schema=None) as batch_op:
        batch_op.drop_constraint("fk_club_events_created_by", type_="foreignkey")
        batch_op.drop_column("created_by")
        batch_op.drop_column("color")
        batch_op.drop_column("cover_image_url")
        batch_op.drop_column("is_public")
        batch_op.drop_column("requires_approval")
        batch_op.drop_column("cancellation_deadline")
        batch_op.drop_column("registration_deadline")
        batch_op.drop_column("max_attendees")
        batch_op.drop_column("category")
        batch_op.drop_column("all_day")
        batch_op.drop_column("end_date")
        batch_op.drop_column("meeting_url")
        batch_op.drop_column("description")
