"""Celery defaults and the per-process Postgres limits."""

from __future__ import annotations

from hubra.core import db_limits
from hubra.core.tasks import VISIBILITY_TIMEOUT, celery_app, worker_defaults


def test_every_task_has_time_limits_and_late_acks():
    conf = worker_defaults()
    assert 0 < conf["task_soft_time_limit"] < conf["task_time_limit"]
    assert conf["task_acks_late"] is True
    assert conf["worker_prefetch_multiplier"] == 1
    assert conf["task_ignore_result"] is True
    assert conf["broker_transport_options"]["visibility_timeout"] == VISIBILITY_TIMEOUT


def test_soft_limit_from_the_environment(monkeypatch):
    monkeypatch.setenv("CELERY_TASK_SOFT_TIME_LIMIT", "120")
    conf = worker_defaults()
    assert conf["task_soft_time_limit"] == 120
    assert conf["task_time_limit"] == 180


def test_late_acked_tasks_end_before_redis_redelivers_them():
    """A late-acked task still running after the visibility timeout would be
    handed to a second worker and run twice."""
    celery_app.loader.import_default_modules()
    default_hard = celery_app.conf.task_time_limit
    for name, task in celery_app.tasks.items():
        if name.startswith("celery."):
            continue
        acks_late = task.acks_late if task.acks_late is not None else True
        hard = task.time_limit or default_hard
        if acks_late:
            assert hard < VISIBILITY_TIMEOUT, name


def test_webhook_retries_wait_less_than_the_visibility_timeout():
    from hubra.core import webhooks

    assert max(webhooks.RETRY_DELAYS) < VISIBILITY_TIMEOUT


def test_backups_are_not_late_acked():
    from hubra.core.tasks import backup_tasks

    for task in (
        backup_tasks.create_backup_task,
        backup_tasks.restore_club_backup_task,
        backup_tasks.create_scheduled_backups_task,
        backup_tasks.verify_backup_task,
    ):
        assert task.acks_late is False


def test_db_limits_per_process(monkeypatch):
    assert db_limits.limits(None) == {}
    assert db_limits.limits("api") == {"statement": 60_000, "idle_in_tx": 120_000}
    assert db_limits.limits("worker")["idle_in_tx"] == 0
    monkeypatch.setenv("DB_STATEMENT_TIMEOUT_MS_API", "5000")
    assert db_limits.limits("api")["statement"] == 5000
    monkeypatch.setenv("DB_STATEMENT_TIMEOUT_MS_API", "nope")
    assert db_limits.limits("api")["statement"] == 60_000


def test_db_limits_set_on_postgres_connections_only(monkeypatch):
    calls = []

    class Cursor:
        def execute(self, sql):
            calls.append(sql)

        def close(self):
            pass

    class PgConn:
        def cursor(self):
            return Cursor()

        def commit(self):
            calls.append("commit")

    PgConn.__module__ = "psycopg2.extensions"

    class SqliteConn(PgConn):
        pass

    SqliteConn.__module__ = "sqlite3"

    monkeypatch.setattr(db_limits, "_kind", "api")
    db_limits._on_connect(SqliteConn(), None)
    assert calls == []
    db_limits._on_connect(PgConn(), None)
    assert calls == [
        "SET statement_timeout = 60000",
        "SET idle_in_transaction_session_timeout = 120000",
        "commit",
    ]
    calls.clear()
    monkeypatch.setattr(db_limits, "_kind", None)  # the CLI
    db_limits._on_connect(PgConn(), None)
    assert calls == []


def test_an_unregistered_job_counts_as_failed(monkeypatch):
    from hubra.core.services import job_monitor
    from hubra.core.tasks import job_signals

    counted, kept = [], []
    monkeypatch.setattr(
        job_monitor, "count", lambda t, w, ms=None: counted.append((t, w))
    )
    monkeypatch.setattr(job_monitor, "failed", lambda **kw: kept.append(kw))
    job_signals._unknown(name="hubra_payments.tasks.sync_open", id="t1")
    assert counted == [("hubra_payments.tasks.sync_open", "failed")]
    assert "not registered" in str(kept[0]["exception"])
