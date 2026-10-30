"""Every member has a join date

Club owners and members who joined through the club's join page (or were
added by a platform manager) were made without ``members.joined``, so
"Member since" showed nothing. New members now get today's date; this
fills the gap for existing ones with the day their member row was made.

Revision ID: a9c4e2f7d1b6
Revises: e5a1c7f3b9d4
Create Date: 2026-10-30 08:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a9c4e2f7d1b6"
down_revision = "e5a1c7f3b9d4"
branch_labels = None
depends_on = None


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
    bind = op.get_bind()
    postgres = bind.dialect.name == "postgresql"
    day = "CAST(created_at AS DATE)" if postgres else "date(created_at)"
    for schema in _schemas():
        table = f'"{schema}".members' if schema else "members"
        bind.execute(
            sa.text(f"UPDATE {table} SET joined = {day} WHERE joined IS NULL")
        )


def downgrade():
    # The filled-in dates can't be told apart from real ones; leave them.
    pass
