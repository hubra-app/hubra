"""add external_parties and invoice purpose/external_party_id

Revision ID: 19bb18b6212e
Revises: c9349c59585c
Create Date: 2026-07-07 09:58:33.166656

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "19bb18b6212e"
down_revision = "c9349c59585c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "external_parties",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("address_street", sa.String(length=255), nullable=True),
        sa.Column("address_house_no", sa.String(length=50), nullable=True),
        sa.Column("address_postal_code", sa.String(length=20), nullable=True),
        sa.Column("address_city", sa.String(length=255), nullable=True),
        sa.Column(
            "address_country", sa.String(length=2), nullable=False, server_default="CH"
        ),
        sa.Column("notes", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Drop deprecated mail_aliases table (no longer in models).
    with op.batch_alter_table("mail_aliases", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_mail_aliases_primary_mma_id"))
    op.drop_table("mail_aliases")

    with op.batch_alter_table("invoices", schema=None) as batch_op:
        batch_op.add_column(sa.Column("external_party_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "purpose",
                sa.String(length=20),
                nullable=False,
                server_default="membership",
            )
        )
        batch_op.create_foreign_key(
            "fk_invoices_external_party_id",
            "external_parties",
            ["external_party_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade():
    with op.batch_alter_table("invoices", schema=None) as batch_op:
        batch_op.drop_constraint("fk_invoices_external_party_id", type_="foreignkey")
        batch_op.drop_column("purpose")
        batch_op.drop_column("external_party_id")

    # Recreate deprecated mail_aliases table.
    op.create_table(
        "mail_aliases",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("primary_mma_id", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column(
            "address", sa.VARCHAR(length=255), autoincrement=False, nullable=False
        ),
        sa.Column(
            "provisioning_status",
            sa.VARCHAR(length=20),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("created_by_id", sa.INTEGER(), autoincrement=False, nullable=True),
        sa.Column(
            "is_enabled",
            sa.BOOLEAN(),
            server_default=sa.text("true"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "wildduck_id", sa.VARCHAR(length=255), autoincrement=False, nullable=True
        ),
        sa.Column(
            "wildduck_type", sa.VARCHAR(length=20), autoincrement=False, nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["members.id"],
            name=op.f("mail_aliases_created_by_id_fkey"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["primary_mma_id"],
            ["managed_mail_addresses.id"],
            name=op.f("mail_aliases_primary_mma_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("mail_aliases_pkey")),
        sa.UniqueConstraint(
            "address",
            name=op.f("mail_aliases_address_key"),
            postgresql_include=[],
            postgresql_nulls_not_distinct=False,
        ),
    )
    with op.batch_alter_table("mail_aliases", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_mail_aliases_primary_mma_id"),
            ["primary_mma_id"],
            unique=False,
        )

    op.drop_table("external_parties")
