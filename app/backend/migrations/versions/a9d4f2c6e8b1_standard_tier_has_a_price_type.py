"""The seeded Standard tier has a price type

New clubs got a "Standard" tier without ``price_type``. Pricing only bills
"fixed", "percentage" and "formula" tiers, and the club app's tier form
requires one of them, so the tier could not be saved as it was shown and
billed nothing whatever price it got through the API. This sets "fixed"
(the form's default) where it is missing in every club.

Revision ID: a9d4f2c6e8b1
Revises: f3c8e1a7b5d2
Create Date: 2026-10-29 01:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a9d4f2c6e8b1"
down_revision = "f3c8e1a7b5d2"
branch_labels = None
depends_on = None


def _schemas():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return []
    return list(
        bind.execute(
            sa.text(
                "SELECT table_schema FROM information_schema.tables "
                "WHERE table_name = 'membership_tiers' ORDER BY table_schema"
            )
        ).scalars()
    )


def upgrade():
    for schema in _schemas():
        op.execute(
            f"UPDATE {schema}.membership_tiers SET price_type = 'fixed' "
            "WHERE price_type IS NULL"
        )


def downgrade():
    # Which tiers had no type is not kept; "fixed" is what they priced as
    # in the form anyway.
    pass
