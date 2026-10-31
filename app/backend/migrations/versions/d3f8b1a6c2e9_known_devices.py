"""known_devices: browsers an account signed in from (new-device mail)

Each browser carries a random token in the hubra_device cookie; the table
keeps its hash per account.  A sign-in without a known token sends the
account a "new sign-in" mail.

Safe to run again per club (flask migrate-tenants): the table goes to
public, once.

Revision ID: d3f8b1a6c2e9
Revises: d7f3b9a1c5e8, e3b9d5f1a7c4 (also joins the two heads on main)
Create Date: 2026-10-31 07:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d3f8b1a6c2e9"
down_revision = ("d7f3b9a1c5e8", "e3b9d5f1a7c4")
branch_labels = None
depends_on = None


def _public_schema():
    return "public" if op.get_bind().dialect.name == "postgresql" else None


def _has_table(table, schema):
    return sa.inspect(op.get_bind()).has_table(table, schema=schema)


def upgrade():
    schema = _public_schema()
    if _has_table("known_devices", schema):
        return
    op.create_table(
        "known_devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("browser_family", sa.String(length=50), nullable=True),
        sa.Column("platform", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "token_hash"),
        schema=schema,
    )
    op.create_index(
        "ix_known_devices_user_id", "known_devices", ["user_id"], schema=schema
    )


def downgrade():
    schema = _public_schema()
    if _has_table("known_devices", schema):
        op.drop_table("known_devices", schema=schema)
