"""Each club counts its own ids

Club tables are cloned with ``LIKE public.<t> INCLUDING ALL``; the core
tables use SERIAL, so every club's id defaults still drew from public's
sequences and all clubs shared one counter per table. Invoice and member
numbers jumped with other clubs' activity, core migrations that drop a table
could not be rolled back once clubs existed, and a club's data could not
move to another instance without collisions.

Every id column of each club schema gets ``<schema>.<table>_<column>_seq``,
started after the highest id already there. New clubs get theirs in
``schema_manager._own_sequences``. Plugin tables are migrated per schema by
their plugins and already have their own.

Revision ID: d7b3f9e1a5c2
Revises: c4e8a2d6f1b3
Create Date: 2026-10-29 07:45:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d7b3f9e1a5c2"
down_revision = "c4e8a2d6f1b3"
branch_labels = None
depends_on = None


def _club_schemas(bind):
    return list(
        bind.execute(
            sa.text(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name LIKE 'tenant\\_%' ORDER BY schema_name"
            )
        ).scalars()
    )


def _serial_columns(bind, schema, pattern):
    return bind.execute(
        sa.text(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = :schema AND column_default LIKE :pattern"
        ),
        {"schema": schema, "pattern": pattern},
    ).all()


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for schema in _club_schemas(bind):
        for table, column in _serial_columns(bind, schema, "nextval(%"):
            seq = f"{schema}.{table}_{column}_seq"
            if f"'{seq}'" in (
                bind.execute(
                    sa.text(
                        "SELECT column_default FROM information_schema.columns "
                        "WHERE table_schema = :s AND table_name = :t "
                        "AND column_name = :c"
                    ),
                    {"s": schema, "t": table, "c": column},
                ).scalar()
                or ""
            ):
                continue  # already its own
            op.execute(f"CREATE SEQUENCE IF NOT EXISTS {seq}")
            op.execute(
                f"SELECT setval('{seq}', "
                f"COALESCE((SELECT MAX({column}) FROM {schema}.{table}), 0) + 1, false)"
            )
            op.execute(
                f"ALTER TABLE {schema}.{table} ALTER COLUMN {column} "
                f"SET DEFAULT nextval('{seq}'::regclass)"
            )
            op.execute(f"ALTER SEQUENCE {seq} OWNED BY {schema}.{table}.{column}")


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for schema in _club_schemas(bind):
        for table, column in _serial_columns(
            bind, schema, f"nextval('{schema}.%"
        ):
            public_seq = bind.execute(
                sa.text("SELECT pg_get_serial_sequence(:t, :c)"),
                {"t": f"public.{table}", "c": column},
            ).scalar()
            if public_seq is None:
                continue  # a plugin's table: it keeps its own
            # Back on the shared counter, which must not hand out an id the
            # club already has.
            op.execute(
                f"SELECT setval('{public_seq}', GREATEST("
                f"(SELECT last_value FROM {public_seq}), "
                f"COALESCE((SELECT MAX({column}) FROM {schema}.{table}), 1)))"
            )
            op.execute(
                f"ALTER TABLE {schema}.{table} ALTER COLUMN {column} "
                f"SET DEFAULT nextval('{public_seq}'::regclass)"
            )
            op.execute(f"DROP SEQUENCE IF EXISTS {schema}.{table}_{column}_seq")
