"""Privacy self-service (revDSG)

``members.photo_consent`` records whether the club may show photos of a
member (None: never asked) and ``member_consents`` logs every change of a
consent. Added to the template tables in public and to every club schema.

Revision ID: a5c9e3b7d1f2
Revises: a9c3e5f7b1d4
Create Date: 2026-11-05 23:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a5c9e3b7d1f2"
down_revision = "a9c3e5f7b1d4"
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


def _json():
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.JSONB()
    return sa.JSON()


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        ref = f"{schema}." if schema else ""
        have = {c["name"] for c in inspector.get_columns("members", schema=schema)}
        if "photo_consent" not in have:
            op.add_column(
                "members",
                sa.Column("photo_consent", sa.Boolean(), nullable=True),
                schema=schema,
            )
        if not inspector.has_table("member_consents", schema=schema):
            op.create_table(
                "member_consents",
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column(
                    "member_id",
                    sa.Integer(),
                    sa.ForeignKey(f"{ref}members.id", ondelete="CASCADE"),
                    nullable=False,
                ),
                sa.Column("kind", sa.String(30), nullable=False),
                sa.Column("value", _json(), nullable=True),
                sa.Column("changed_by", sa.Integer(), nullable=True),
                sa.Column("source", sa.String(20), nullable=False),
                sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                schema=schema,
            )
            op.create_index(
                "ix_member_consents_member_id",
                "member_consents",
                ["member_id"],
                schema=schema,
            )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        if inspector.has_table("member_consents", schema=schema):
            op.drop_table("member_consents", schema=schema)
        have = {c["name"] for c in inspector.get_columns("members", schema=schema)}
        if "photo_consent" in have:
            op.drop_column("members", "photo_consent", schema=schema)
