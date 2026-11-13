"""Migrations from parallel pull requests may end in several heads.

Each pull request adds its migration on the head it saw, so two of them merged
in a row leave two heads. That is fine: deploys run ``flask db upgrade heads``
and Alembic applies both branches. What is not fine is two unjoined branches
changing the same table, because their order is then up to Alembic. This test
fails in that case; give the later migration the other one as down_revision (or
add a merge migration). See docs/migrations.md.
"""

import ast
import itertools
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"

# op.<name>(...) -> position of the table name argument.
TABLE_ARG = {
    "create_table": 0,
    "drop_table": 0,
    "rename_table": 0,
    "add_column": 0,
    "drop_column": 0,
    "alter_column": 0,
    "batch_alter_table": 0,
    "create_unique_constraint": 1,
    "create_check_constraint": 1,
    "drop_constraint": 1,
    "create_index": 1,
    "drop_index": 1,
    "create_foreign_key": 1,
}


def _script() -> ScriptDirectory:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    return ScriptDirectory.from_config(config)


def tables_touched(path: Path) -> set[str]:
    """Tables a migration's upgrade() changes (op.execute SQL is not read)."""
    tree = ast.parse(path.read_text())
    upgrade = next(
        (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "upgrade"),
        None,
    )
    if upgrade is None:
        return set()
    tables: set[str] = set()
    for node in ast.walk(upgrade):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "op"
            and node.func.attr in TABLE_ARG
        ):
            continue
        arg = None
        for kw in node.keywords:
            if kw.arg == "table_name":
                arg = kw.value
        pos = TABLE_ARG[node.func.attr]
        if arg is None and len(node.args) > pos:
            arg = node.args[pos]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            tables.add(arg.value)
    return tables


def test_migration_graph_loads():
    # Raises for a down_revision that names no migration, or a duplicate id.
    script = _script()
    assert script.get_heads()


def test_unjoined_heads_change_different_tables():
    script = _script()
    heads = script.get_heads()
    ancestors = {
        h: {r.revision for r in script.iterate_revisions(h, "base")} for h in heads
    }
    clashes = []
    for a, b in itertools.combinations(heads, 2):
        only_a = ancestors[a] - ancestors[b]
        only_b = ancestors[b] - ancestors[a]
        touched_a = {
            t: rev
            for rev in only_a
            for t in tables_touched(Path(script.get_revision(rev).path))
        }
        touched_b = {
            t: rev
            for rev in only_b
            for t in tables_touched(Path(script.get_revision(rev).path))
        }
        for table in sorted(touched_a.keys() & touched_b.keys()):
            clashes.append(f"{table}: {touched_a[table]} and {touched_b[table]}")
    assert not clashes, (
        "unjoined migration heads change the same table; let one follow the "
        "other (down_revision) or add a merge migration: " + "; ".join(clashes)
    )


def test_tables_touched_reads_op_calls(tmp_path):
    path = tmp_path / "m.py"
    path.write_text(
        "from alembic import op\n"
        "def upgrade():\n"
        "    op.create_table('a')\n"
        "    with op.batch_alter_table('b') as batch_op:\n"
        "        batch_op.add_column(None)\n"
        "    op.create_index('ix_c_x', 'c', ['x'])\n"
        "    op.drop_index('ix_d_x', table_name='d')\n"
        "def downgrade():\n"
        "    op.drop_table('z')\n"
    )
    assert tables_touched(path) == {"a", "b", "c", "d"}


def test_flask_db_commands_default_to_every_head():
    import flask_migrate.cli as cli

    import hubra.core.extensions  # noqa: F401  (sets the defaults)

    defaults = {
        (cmd.name, p.name): p.default
        for cmd in (cli.upgrade, cli.migrate, cli.revision)
        for p in cmd.params
        if p.name in ("revision", "head")
    }
    assert defaults == {
        ("upgrade", "revision"): "heads",
        ("migrate", "head"): "heads",
        ("revision", "head"): "heads",
    }
