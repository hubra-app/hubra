"""Stored files: the record of each file in Hubra's file store

Public schema. ``stored_files`` lists every file a club keeps in the file
store (``hubra.core.files``): its key, owner (module or plugin), size and
type, so the club's storage counts them and deleting a club deletes them.

Revision ID: d5a7c3e9f1b4
Revises: b9e3f1a7c5d2
Create Date: 2026-11-05 09:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "d5a7c3e9f1b4"
down_revision = "b9e3f1a7c5d2"
branch_labels = None
depends_on = None


def upgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "stored_files" in tables:
        return
    op.create_table(
        "stored_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("key", sa.String(255), nullable=False, unique=True),
        sa.Column("owner", sa.String(64), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "content_type",
            sa.String(255),
            nullable=False,
            server_default="application/octet-stream",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_stored_files_tenant_id", "stored_files", ["tenant_id"])


def downgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "stored_files" in tables:
        op.drop_index("ix_stored_files_tenant_id", table_name="stored_files")
        op.drop_table("stored_files")
