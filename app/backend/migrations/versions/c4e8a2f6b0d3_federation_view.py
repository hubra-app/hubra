"""Federation view: associations and their member clubs

``federation_links`` (public only) links an association to its member
clubs; ``club_events.federation_shared`` marks an association's event for its
member clubs (template tables in public and every club schema).

Revision ID: c4e8a2f6b0d3
Revises: b7d1f3a9c5e2
Create Date: 2026-11-05 23:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "c4e8a2f6b0d3"
down_revision = "b7d1f3a9c5e2"
branch_labels = None
depends_on = None


def _schemas():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return [None]
    rows = bind.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'club_events' ORDER BY table_schema"
        )
    ).scalars()
    return list(rows)


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("federation_links"):
        op.create_table(
            "federation_links",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "federation_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "club_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column(
                "share_contacts",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("invited_by", sa.String(255), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("federation_id", "club_id"),
        )
        op.create_index(
            "ix_federation_links_federation_id", "federation_links", ["federation_id"]
        )
        op.create_index("ix_federation_links_club_id", "federation_links", ["club_id"])
    for schema in _schemas():
        have = {c["name"] for c in inspector.get_columns("club_events", schema=schema)}
        if "federation_shared" not in have:
            op.add_column(
                "club_events",
                sa.Column(
                    "federation_shared",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("false"),
                ),
                schema=schema,
            )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for schema in _schemas():
        have = {c["name"] for c in inspector.get_columns("club_events", schema=schema)}
        if "federation_shared" in have:
            op.drop_column("club_events", "federation_shared", schema=schema)
    if inspector.has_table("federation_links"):
        op.drop_table("federation_links")
