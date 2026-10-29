"""The migrations end in one head, or ``flask db upgrade`` refuses to run.

Two pull requests that each add a migration on the same parent leave two
heads once both are merged; the test suite builds its tables without
Alembic, so only the Compose smoke test noticed.
"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_migrations_have_one_head():
    migrations = Path(__file__).resolve().parents[1] / "migrations"
    config = Config()
    config.set_main_option("script_location", str(migrations))
    heads = ScriptDirectory.from_config(config).get_heads()
    assert len(heads) == 1, f"several migration heads: {heads}; add a merge migration"
