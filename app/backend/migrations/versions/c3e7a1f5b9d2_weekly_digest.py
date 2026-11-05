"""Weekly digest mail

``members.weekly_digest_mail`` lets a member ask for a weekly summary of
the club by mail (off by default); ``members.digest_sent_at`` records when
the last one went out, so each week sends one. Added to the template tables
in public and to every club schema.

Revision ID: c3e7a1f5b9d2
Revises: b8d2f6a4c9e1
Create Date: 2026-11-05 20:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c3e7a1f5b9d2"
down_revision = "b8d2f6a4c9e1"
branch_labels = None
depends_on = None

COLUMNS = [
    (
        "weekly_digest_mail",
        sa.Boolean,
        {"nullable": False, "server_default": sa.false()},
    ),
    ("digest_sent_at", lambda: sa.DateTime(timezone=True), {"nullable": True}),
]


def _schemas():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return [None]
    rows = bind.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'members' ORDER BY table_schema"
        )
    ).scalars()
    return list(rows)


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        have = {c["name"] for c in inspector.get_columns("members", schema=schema)}
        for name, type_, kwargs in COLUMNS:
            if name not in have:
                op.add_column(
                    "members", sa.Column(name, type_(), **kwargs), schema=schema
                )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        have = {c["name"] for c in inspector.get_columns("members", schema=schema)}
        for name, _type, _kwargs in COLUMNS:
            if name in have:
                op.drop_column("members", name, schema=schema)
