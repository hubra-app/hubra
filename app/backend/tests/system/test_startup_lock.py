"""startup_lock waits for Postgres instead of failing on the first try."""

import pytest
from sqlalchemy.exc import OperationalError

from hubra.core import startup_lock


class _Engine:
    def __init__(self, failures):
        self.failures = failures
        self.calls = 0

    def connect(self):
        self.calls += 1
        if self.calls <= self.failures:
            raise OperationalError("connect", {}, Exception("connection refused"))
        return "conn"


def test_retries_until_postgres_takes_connections(monkeypatch):
    monkeypatch.setattr(startup_lock.time, "sleep", lambda s: None)
    engine = _Engine(failures=3)
    assert startup_lock._connect(engine, wait=60) == "conn"
    assert engine.calls == 4


def test_gives_up_after_the_wait(monkeypatch):
    monkeypatch.setattr(startup_lock.time, "sleep", lambda s: None)
    engine = _Engine(failures=10**6)
    with pytest.raises(OperationalError):
        startup_lock._connect(engine, wait=0)
    assert engine.calls == 1
