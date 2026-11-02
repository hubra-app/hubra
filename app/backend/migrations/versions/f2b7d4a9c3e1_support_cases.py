"""Support cases: problem reports, feature requests, votes and comments

Public schema. People send problem reports and feature requests from the
club app; platform staff answer, close, merge and publish them in manage.
Feature requests on the public roadmap get votes.

Revision ID: f2b7d4a9c3e1
Revises: c4f8a2d6e9b1
Create Date: 2026-11-02 09:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f2b7d4a9c3e1"
down_revision = "c4f8a2d6e9b1"
branch_labels = None
depends_on = None


def _json():
    return postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "support_cases" not in tables:
        op.create_table(
            "support_cases",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("kind", sa.String(10), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="open"),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("details", _json(), nullable=True),
            sa.Column("area", sa.String(40), nullable=True),
            sa.Column("severity", sa.String(20), nullable=True),
            sa.Column("page", sa.String(300), nullable=True),
            sa.Column("fingerprint", _json(), nullable=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "is_public", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
            sa.Column(
                "merged_into_id",
                sa.Integer(),
                sa.ForeignKey("support_cases.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index("ix_support_cases_kind", "support_cases", ["kind"])
        op.create_index("ix_support_cases_status", "support_cases", ["status"])
        op.create_index("ix_support_cases_user_id", "support_cases", ["user_id"])
        op.create_index(
            "ix_support_cases_merged_into_id", "support_cases", ["merged_into_id"]
        )

    if "support_case_comments" not in tables:
        op.create_table(
            "support_case_comments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "case_id",
                sa.Integer(),
                sa.ForeignKey("support_cases.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column(
                "from_staff", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
            sa.Column(
                "internal", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "ix_support_case_comments_case_id", "support_case_comments", ["case_id"]
        )

    if "support_case_votes" not in tables:
        op.create_table(
            "support_case_votes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "case_id",
                sa.Integer(),
                sa.ForeignKey("support_cases.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint("case_id", "user_id", name="uq_support_case_vote"),
        )
        op.create_index(
            "ix_support_case_votes_case_id", "support_case_votes", ["case_id"]
        )


def downgrade():
    op.drop_table("support_case_votes")
    op.drop_table("support_case_comments")
    op.drop_table("support_cases")
