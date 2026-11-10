"""Groups give roles, functions held per group, groups per tier

* ``group_roles``: the roles a group gives everyone in it, for the whole club.
* ``functions.per_group``: a group function (Trainer/in) is held per group;
  ``function_holders.group_id`` names the group. Its roles count in that
  group only. The unique function + member becomes two partial unique
  indexes: once per member for a club function, once per member and group
  for a group function.
* ``tier_groups``: the groups a tier's members are in.

``groups.is_default`` (new members join the group) already exists.

Added to the template tables in public and to every club schema.

Revision ID: f4c2a8e6b1d3
Revises: 449652170fd4
Create Date: 2026-11-10 10:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f4c2a8e6b1d3"
down_revision = "449652170fd4"
branch_labels = None
depends_on = None


def _schemas():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return [None]
    rows = bind.execute(
        sa.text(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = 'function_holders' ORDER BY table_schema"
        )
    ).scalars()
    return list(rows)


def _q(schema, table):
    return f'"{schema}"."{table}"' if schema else table


def _link_table(name, left, left_ref, right, right_ref, schema):
    ref = f"{schema}." if schema else ""
    op.create_table(
        name,
        sa.Column(
            left,
            sa.Integer(),
            sa.ForeignKey(f"{ref}{left_ref}.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            right,
            sa.Integer(),
            sa.ForeignKey(f"{ref}{right_ref}.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        schema=schema,
    )
    op.create_index(f"ix_{name}_{right}", name, [right], schema=schema)


def upgrade():
    bind = op.get_bind()
    postgres = bind.dialect.name == "postgresql"
    for schema in _schemas():
        inspector = sa.inspect(bind)
        if not inspector.has_table("groups", schema=schema):
            continue
        if not inspector.has_table("group_roles", schema=schema):
            _link_table("group_roles", "group_id", "groups", "role_id", "roles", schema)
        if not inspector.has_table(
            "tier_groups", schema=schema
        ) and inspector.has_table("membership_tiers", schema=schema):
            _link_table(
                "tier_groups",
                "tier_id",
                "membership_tiers",
                "group_id",
                "groups",
                schema,
            )

        fn_cols = {c["name"] for c in inspector.get_columns("functions", schema=schema)}
        if "per_group" not in fn_cols:
            op.add_column(
                "functions",
                sa.Column(
                    "per_group", sa.Boolean(), nullable=False, server_default=sa.false()
                ),
                schema=schema,
            )

        holder_cols = {
            c["name"] for c in inspector.get_columns("function_holders", schema=schema)
        }
        if "group_id" not in holder_cols:
            op.add_column(
                "function_holders",
                sa.Column("group_id", sa.Integer(), nullable=True),
                schema=schema,
            )
            op.create_index(
                "ix_function_holders_group_id",
                "function_holders",
                ["group_id"],
                schema=schema,
            )
        if not postgres:
            continue  # SQLite builds the table from the models

        # The old unique (function_id, member_id): a constraint in public, an
        # index of the same shape in club schemas cloned with LIKE.
        for uc in inspector.get_unique_constraints("function_holders", schema=schema):
            if sorted(uc["column_names"]) == ["function_id", "member_id"]:
                bind.execute(
                    sa.text(
                        f"ALTER TABLE {_q(schema, 'function_holders')} "
                        f'DROP CONSTRAINT IF EXISTS "{uc["name"]}"'
                    )
                )
        index_names = set()
        for ix in sa.inspect(bind).get_indexes("function_holders", schema=schema):
            index_names.add(ix["name"])
            if (
                ix.get("unique")
                and sorted(ix["column_names"])
                == [
                    "function_id",
                    "member_id",
                ]
                and not ix["name"].startswith("uq_function_holders_")
            ):
                prefix = f'"{schema}".' if schema else ""
                bind.execute(sa.text(f'DROP INDEX IF EXISTS {prefix}"{ix["name"]}"'))
        if "uq_function_holders_club" not in index_names:
            bind.execute(
                sa.text(
                    "CREATE UNIQUE INDEX uq_function_holders_club ON "
                    f"{_q(schema, 'function_holders')} (function_id, member_id) "
                    "WHERE group_id IS NULL"
                )
            )
        if "uq_function_holders_group" not in index_names:
            bind.execute(
                sa.text(
                    "CREATE UNIQUE INDEX uq_function_holders_group ON "
                    f"{_q(schema, 'function_holders')} (function_id, member_id, group_id) "
                    "WHERE group_id IS NOT NULL"
                )
            )


def downgrade():
    bind = op.get_bind()
    postgres = bind.dialect.name == "postgresql"
    for schema in _schemas():
        inspector = sa.inspect(bind)
        for table in ("group_roles", "tier_groups"):
            if inspector.has_table(table, schema=schema):
                op.drop_table(table, schema=schema)
        if postgres:
            prefix = f'"{schema}".' if schema else ""
            # Group function holders go: the old constraint allows one row
            # per member and function.
            bind.execute(
                sa.text(
                    f"DELETE FROM {_q(schema, 'function_holders')} WHERE group_id IS NOT NULL"
                )
            )
            for name in ("uq_function_holders_club", "uq_function_holders_group"):
                bind.execute(sa.text(f"DROP INDEX IF EXISTS {prefix}{name}"))
            bind.execute(
                sa.text(
                    f"ALTER TABLE {_q(schema, 'function_holders')} ADD CONSTRAINT "
                    "function_holders_function_id_member_id_key UNIQUE (function_id, member_id)"
                )
            )
        holder_cols = {
            c["name"] for c in inspector.get_columns("function_holders", schema=schema)
        }
        if "group_id" in holder_cols:
            op.drop_index(
                "ix_function_holders_group_id",
                table_name="function_holders",
                schema=schema,
            )
            op.drop_column("function_holders", "group_id", schema=schema)
        fn_cols = {c["name"] for c in inspector.get_columns("functions", schema=schema)}
        if "per_group" in fn_cols:
            op.drop_column("functions", "per_group", schema=schema)
