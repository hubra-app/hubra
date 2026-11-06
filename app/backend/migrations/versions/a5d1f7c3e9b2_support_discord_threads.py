"""Support cases on Discord: a thread per case, people on a case

``support_cases.discord_thread_id`` and ``discord_last_message_id`` (the
case's private thread on the platform's Discord server and the newest message
read from it), ``support_case_comments.discord_message_id`` (nothing is copied
twice), and the table ``support_case_people`` (people added to a case besides
its reporter, and where they stand in the thread).

Public-schema only, so the revision is safe to run again per club
(flask migrate-tenants).

Revision ID: a5d1f7c3e9b2
Revises: e4a9c2f6b1d8
Create Date: 2026-11-05 23:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a5d1f7c3e9b2"
down_revision = "e4a9c2f6b1d8"
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
    have = _columns("support_cases", schema)
    if have is None:
        return
    for name in ("discord_thread_id", "discord_last_message_id"):
        if name not in have:
            op.add_column(
                "support_cases",
                sa.Column(name, sa.String(length=32), nullable=True),
                schema=schema,
            )
    have = _columns("support_case_comments", schema)
    if have is not None and "discord_message_id" not in have:
        op.add_column(
            "support_case_comments",
            sa.Column("discord_message_id", sa.String(length=32), nullable=True),
            schema=schema,
        )
        op.create_index(
            "ix_support_case_comments_discord_message_id",
            "support_case_comments",
            ["discord_message_id"],
            schema=schema,
        )
    if _columns("support_case_people", schema) is None:
        prefix = f"{schema}." if schema else ""
        op.create_table(
            "support_case_people",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "case_id",
                sa.Integer(),
                sa.ForeignKey(f"{prefix}support_cases.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey(f"{prefix}users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "added_by",
                sa.Integer(),
                sa.ForeignKey(f"{prefix}users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "discord", sa.String(length=20), nullable=False, server_default=""
            ),
            sa.Column("invite_code", sa.String(length=32), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("case_id", "user_id", name="uq_support_case_person"),
            schema=schema,
        )
        op.create_index(
            "ix_support_case_people_case_id",
            "support_case_people",
            ["case_id"],
            schema=schema,
        )
        op.create_index(
            "ix_support_case_people_user_id",
            "support_case_people",
            ["user_id"],
            schema=schema,
        )


def downgrade():
    schema = _public_schema()
    if _columns("support_case_people", schema) is not None:
        op.drop_table("support_case_people", schema=schema)
    have = _columns("support_case_comments", schema)
    if have is not None and "discord_message_id" in have:
        op.drop_index(
            "ix_support_case_comments_discord_message_id",
            table_name="support_case_comments",
            schema=schema,
        )
        op.drop_column("support_case_comments", "discord_message_id", schema=schema)
    have = _columns("support_cases", schema)
    for name in ("discord_last_message_id", "discord_thread_id"):
        if have is not None and name in have:
            op.drop_column("support_cases", name, schema=schema)
