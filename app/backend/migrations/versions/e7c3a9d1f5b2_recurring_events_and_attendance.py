"""Recurring events and attendance

``event_series`` holds a weekly rule; each of its dates is an event with
``club_events.series_id`` and ``series_date``. ``club_events.group_id`` names
the group an event is for. ``event_attendance`` records who was there per
event, and is filled from registrations already marked "attended". Added to
the template tables in public and to every club schema. Also joins the two
heads from #80 and #82.

Revision ID: e7c3a9d1f5b2
Revises: d8f2b6a4c1e9, f2c8a4d6b1e3
Create Date: 2026-10-31 07:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e7c3a9d1f5b2"
down_revision = ("d8f2b6a4c1e9", "f2c8a4d6b1e3")
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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for schema in _schemas():
        ref = f"{schema}." if schema else ""
        if not inspector.has_table("event_series", schema=schema):
            op.create_table(
                "event_series",
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("start_date", sa.Date(), nullable=False),
                sa.Column("until", sa.Date(), nullable=False),
                sa.Column("interval", sa.Integer(), nullable=False),
                sa.Column("weekdays", sa.JSON(), nullable=False),
                sa.Column("skip_dates", sa.JSON(), nullable=False),
                sa.Column(
                    "created_by",
                    sa.Integer(),
                    sa.ForeignKey(f"{ref}members.id", ondelete="SET NULL"),
                    nullable=True,
                ),
                sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                schema=schema,
            )

        have = {c["name"] for c in inspector.get_columns("club_events", schema=schema)}
        if "group_id" not in have:
            op.add_column(
                "club_events",
                sa.Column(
                    "group_id",
                    sa.Integer(),
                    sa.ForeignKey(f"{ref}groups.id", ondelete="SET NULL"),
                    nullable=True,
                ),
                schema=schema,
            )
            op.create_index(
                "ix_club_events_group_id", "club_events", ["group_id"], schema=schema
            )
        if "series_id" not in have:
            op.add_column(
                "club_events",
                sa.Column(
                    "series_id",
                    sa.Integer(),
                    sa.ForeignKey(f"{ref}event_series.id", ondelete="SET NULL"),
                    nullable=True,
                ),
                schema=schema,
            )
            op.create_index(
                "ix_club_events_series_id", "club_events", ["series_id"], schema=schema
            )
        if "series_date" not in have:
            op.add_column(
                "club_events",
                sa.Column("series_date", sa.Date(), nullable=True),
                schema=schema,
            )

        if not inspector.has_table("event_attendance", schema=schema):
            op.create_table(
                "event_attendance",
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column(
                    "event_id",
                    sa.Integer(),
                    sa.ForeignKey(f"{ref}club_events.id", ondelete="CASCADE"),
                    nullable=False,
                ),
                sa.Column(
                    "member_id",
                    sa.Integer(),
                    sa.ForeignKey(f"{ref}members.id", ondelete="CASCADE"),
                    nullable=False,
                ),
                sa.Column("status", sa.String(20), nullable=False),
                sa.Column(
                    "marked_by",
                    sa.Integer(),
                    sa.ForeignKey(f"{ref}members.id", ondelete="SET NULL"),
                    nullable=True,
                ),
                sa.Column("marked_at", sa.DateTime(timezone=True), nullable=False),
                sa.UniqueConstraint("event_id", "member_id", name="uq_event_attendance"),
                schema=schema,
            )
            for column in ("event_id", "member_id"):
                op.create_index(
                    f"ix_event_attendance_{column}",
                    "event_attendance",
                    [column],
                    schema=schema,
                )
            # Attendance marked on a registration so far.
            bind.execute(
                sa.text(
                    f"INSERT INTO {ref}event_attendance "
                    "(event_id, member_id, status, marked_at) "
                    "SELECT r.event_id, r.member_id, 'present', "
                    "COALESCE(r.attended_at, r.registered_at) "
                    f"FROM {ref}event_registrations r "
                    f"JOIN {ref}members m ON m.id = r.member_id "
                    f"JOIN {ref}club_events e ON e.id = r.event_id "
                    "WHERE r.status = 'attended'"
                )
            )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        if inspector.has_table("event_attendance", schema=schema):
            op.drop_table("event_attendance", schema=schema)
        have = {c["name"] for c in inspector.get_columns("club_events", schema=schema)}
        for column in ("series_date", "series_id", "group_id"):
            if column in have:
                if column != "series_date":
                    op.drop_index(
                        f"ix_club_events_{column}", "club_events", schema=schema
                    )
                op.drop_column("club_events", column, schema=schema)
        if inspector.has_table("event_series", schema=schema):
            op.drop_table("event_series", schema=schema)
