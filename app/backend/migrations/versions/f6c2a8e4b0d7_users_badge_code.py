"""users.badge_code and users.gender

``badge_code`` is the member badge number, one per account, given the first
time the account page shows the badge (so no backfill). ``gender`` is
female, male, diverse or empty, set by the person on the account page.

Public-schema only, so the revision is safe to run again per club
(flask migrate-tenants).

Revision ID: f6c2a8e4b0d7
Revises: e9c4a1f7b3d5
Create Date: 2026-11-09 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f6c2a8e4b0d7"
down_revision = "e9c4a1f7b3d5"
branch_labels = None
depends_on = None


def _public_schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def _columns(table, schema):
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table, schema=schema):
        return None
    return {c["name"] for c in inspector.get_columns(table, schema=schema)}


def upgrade():
    schema = _public_schema()
    have = _columns("users", schema)
    if have is not None and "badge_code" not in have:
        op.add_column(
            "users", sa.Column("badge_code", sa.String(length=16), nullable=True), schema=schema
        )
        op.create_index(
            "uq_users_badge_code", "users", ["badge_code"], unique=True, schema=schema
        )
    if have is not None and "gender" not in have:
        op.add_column(
            "users", sa.Column("gender", sa.String(length=16), nullable=True), schema=schema
        )


def downgrade():
    schema = _public_schema()
    have = _columns("users", schema)
    if have is not None and "gender" in have:
        op.drop_column("users", "gender", schema=schema)
    if have is not None and "badge_code" in have:
        op.drop_index("uq_users_badge_code", table_name="users", schema=schema)
        op.drop_column("users", "badge_code", schema=schema)
