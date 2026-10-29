"""Two branches that each add a migration merge cleanly in git but leave
Alembic with two heads, and ``flask db upgrade`` then refuses to run."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_migrations_have_one_head():
    migrations = Path(__file__).resolve().parents[1] / "migrations"
    config = Config()
    config.set_main_option("script_location", str(migrations))
    heads = ScriptDirectory.from_config(config).get_heads()
    assert len(heads) == 1, f"add a merge migration for {heads}"
