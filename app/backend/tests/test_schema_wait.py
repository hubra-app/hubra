"""python -m hubra.core.schema_wait: the club backend's start-up check in a
split install (docs/platform-backend.md)."""

from __future__ import annotations

from alembic.script import ScriptDirectory

from hubra.core import schema_wait


def _script():
    return ScriptDirectory(str(schema_wait.MIGRATIONS))


def test_at_head_is_ready():
    script = _script()
    assert schema_wait.status(script, set(script.get_heads())) == "ready"


def test_older_revision_is_behind():
    script = _script()
    head = script.get_revision(script.get_heads()[0])
    parent = head.down_revision
    parent = parent[0] if isinstance(parent, tuple) else parent
    assert schema_wait.status(script, {parent}) == "behind"


def test_empty_database_is_behind():
    assert schema_wait.status(_script(), set()) == "behind"


def test_unknown_revision_means_the_platform_is_newer():
    assert schema_wait.status(_script(), {"ffffffffffff"}) == "ahead"


def test_sqlite_returns_at_once(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    assert schema_wait.run(timeout=0) == 0
