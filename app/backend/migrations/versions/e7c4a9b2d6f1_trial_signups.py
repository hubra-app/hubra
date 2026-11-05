"""Trial training sign-ups

``club_events.trial_spots`` opens an event to people who aren't members
yet, and ``trial_signups`` holds their bookings from the club's public
trial page. Added to the template tables in public and to every club
schema.

Revision ID: e7c4a9b2d6f1
Revises: d3a7e5b9c1f4
Create Date: 2026-11-05 18:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "e7c4a9b2d6f1"
down_revision = "d3a7e5b9c1f4"
branch_labels = None
depends_on = None


def _schemas():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return [None]
    rows = bind.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'club_events' ORDER BY table_schema"
        )
    ).scalars()
    return list(rows)


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        ref = f"{schema}." if schema else ""
        have = {c["name"] for c in inspector.get_columns("club_events", schema=schema)}
        if "trial_spots" not in have:
            op.add_column(
                "club_events",
                sa.Column("trial_spots", sa.Integer(), nullable=True),
                schema=schema,
            )
        if not inspector.has_table("trial_signups", schema=schema):
            op.create_table(
                "trial_signups",
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column(
                    "event_id",
                    sa.Integer(),
                    sa.ForeignKey(f"{ref}club_events.id", ondelete="CASCADE"),
                    nullable=False,
                ),
                sa.Column("first_name", sa.String(100), nullable=False),
                sa.Column("last_name", sa.String(100), nullable=False),
                sa.Column("email", sa.String(255), nullable=False),
                sa.Column("phone", sa.String(50), nullable=True),
                sa.Column("birth_date", sa.Date(), nullable=True),
                sa.Column("message", sa.Text(), nullable=True),
                sa.Column("token", sa.String(64), nullable=False, unique=True),
                sa.Column("status", sa.String(20), nullable=False),
                sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                schema=schema,
            )
            op.create_index(
                "ix_trial_signups_event_id",
                "trial_signups",
                ["event_id"],
                schema=schema,
            )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        if inspector.has_table("trial_signups", schema=schema):
            op.drop_table("trial_signups", schema=schema)
        have = {c["name"] for c in inspector.get_columns("club_events", schema=schema)}
        if "trial_spots" in have:
            op.drop_column("club_events", "trial_spots", schema=schema)
