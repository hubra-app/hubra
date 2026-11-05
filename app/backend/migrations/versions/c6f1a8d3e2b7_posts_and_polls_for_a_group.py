"""Posts and polls for one group

``posts.group_id`` and ``polls.group_id`` name the group a post or poll
belongs to, like ``club_events.group_id``. A role held for that group only
(``member_role_scopes``) may then manage it. Added to the template tables in
public and to every club schema.

Revision ID: c6f1a8d3e2b7
Revises: f1c7a3e9b5d2
Create Date: 2026-11-05 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c6f1a8d3e2b7"
down_revision = "f1c7a3e9b5d2"
branch_labels = None
depends_on = None

TABLES = ("posts", "polls")


def _schemas(table: str):
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return [None]
    rows = bind.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = :table ORDER BY table_schema"
        ),
        {"table": table},
    ).scalars()
    return list(rows)


def upgrade():
    inspector = sa.inspect(op.get_bind())
    for table in TABLES:
        for schema in _schemas(table):
            ref = f"{schema}." if schema else ""
            have = {c["name"] for c in inspector.get_columns(table, schema=schema)}
            if "group_id" in have:
                continue
            op.add_column(
                table,
                sa.Column(
                    "group_id",
                    sa.Integer(),
                    sa.ForeignKey(f"{ref}groups.id", ondelete="SET NULL"),
                    nullable=True,
                ),
                schema=schema,
            )
            op.create_index(f"ix_{table}_group_id", table, ["group_id"], schema=schema)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for table in TABLES:
        for schema in _schemas(table):
            have = {c["name"] for c in inspector.get_columns(table, schema=schema)}
            if "group_id" in have:
                # Club schemas are copies of the template, so their index has
                # another name; Postgres drops it with the column anyway.
                if schema is None:
                    op.drop_index(f"ix_{table}_group_id", table)
                op.drop_column(table, "group_id", schema=schema)
