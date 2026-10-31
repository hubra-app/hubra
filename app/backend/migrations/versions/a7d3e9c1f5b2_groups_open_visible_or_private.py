"""Groups are open, visible or private

``groups.visibility`` replaces ``self_join`` and the unused ``is_public``:
"open" (members join and leave on their own, was self_join), "visible"
(the default) and "private" (was is_public false; only members, the lead
and group managers see it). Changed in public and in every club schema.

Revision ID: a7d3e9c1f5b2
Revises: f2c8a4d6b1e3
Create Date: 2026-10-31 06:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a7d3e9c1f5b2"
down_revision = "f2c8a4d6b1e3"
branch_labels = None
depends_on = None


def _schemas():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return [None]
    rows = bind.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'groups' ORDER BY table_schema"
        )
    ).scalars()
    return list(rows)


def _table(schema):
    return f'"{schema}".groups' if schema else "groups"


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for schema in _schemas():
        have = {c["name"] for c in inspector.get_columns("groups", schema=schema)}
        if "visibility" not in have:
            op.add_column(
                "groups",
                sa.Column(
                    "visibility",
                    sa.String(16),
                    nullable=False,
                    server_default="visible",
                ),
                schema=schema,
            )
        if "self_join" in have:
            bind.execute(
                sa.text(f"UPDATE {_table(schema)} SET visibility = 'open' WHERE self_join")
            )
            op.drop_column("groups", "self_join", schema=schema)
        if "is_public" in have:
            bind.execute(
                sa.text(
                    f"UPDATE {_table(schema)} SET visibility = 'private' "
                    "WHERE NOT is_public AND visibility <> 'open'"
                )
            )
            op.drop_column("groups", "is_public", schema=schema)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for schema in _schemas():
        have = {c["name"] for c in inspector.get_columns("groups", schema=schema)}
        if "visibility" not in have:
            continue
        op.add_column(
            "groups",
            sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.true()),
            schema=schema,
        )
        op.add_column(
            "groups",
            sa.Column("self_join", sa.Boolean(), nullable=False, server_default=sa.false()),
            schema=schema,
        )
        bind.execute(
            sa.text(
                f"UPDATE {_table(schema)} SET is_public = visibility <> 'private', "
                "self_join = visibility = 'open'"
            )
        )
        op.drop_column("groups", "visibility", schema=schema)
