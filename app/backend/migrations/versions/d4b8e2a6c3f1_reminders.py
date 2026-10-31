"""Reminders before events and before polls close

``club_events.reminder_sent_at`` and ``polls.reminder_sent_at`` record
when the reminder went out, so each one goes out once.
``members.event_reminder_mail`` and ``members.poll_reminder_mail`` let a
member switch the reminder mails off (on by default). Added to the template
tables in public and to every club schema.

Also joins the two heads that #80 (notifications.link) and #82 (groups
tools count) left on main.

Revision ID: d4b8e2a6c3f1
Revises: d8f2b6a4c1e9, f2c8a4d6b1e3
Create Date: 2026-10-31 07:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d4b8e2a6c3f1"
down_revision = ("d8f2b6a4c1e9", "f2c8a4d6b1e3")
branch_labels = None
depends_on = None

COLUMNS = {
    "club_events": [
        ("reminder_sent_at", lambda: sa.DateTime(timezone=True), {"nullable": True}),
    ],
    "polls": [
        ("reminder_sent_at", lambda: sa.DateTime(timezone=True), {"nullable": True}),
    ],
    "members": [
        (
            "event_reminder_mail",
            sa.Boolean,
            {"nullable": False, "server_default": sa.true()},
        ),
        (
            "poll_reminder_mail",
            sa.Boolean,
            {"nullable": False, "server_default": sa.true()},
        ),
    ],
}


def _schemas(table):
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return [None]
    rows = bind.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = :t ORDER BY table_schema"
        ),
        {"t": table},
    ).scalars()
    return list(rows)


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for table, columns in COLUMNS.items():
        for schema in _schemas(table):
            have = {c["name"] for c in inspector.get_columns(table, schema=schema)}
            for name, type_, kwargs in columns:
                if name not in have:
                    op.add_column(
                        table, sa.Column(name, type_(), **kwargs), schema=schema
                    )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for table, columns in COLUMNS.items():
        for schema in _schemas(table):
            have = {c["name"] for c in inspector.get_columns(table, schema=schema)}
            for name, _type, _kwargs in columns:
                if name in have:
                    op.drop_column(table, name, schema=schema)
