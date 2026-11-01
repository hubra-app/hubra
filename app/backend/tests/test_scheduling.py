"""Scheduled jobs stay single with several beat or worker processes."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from celery.schedules import crontab, schedule

from hubra.core.tasks import scheduling
from hubra.core.tasks.scheduling import (
    HEADER,
    HubraScheduler,
    claim_slot,
    previous_cron_time,
    slot_for,
)

UTC = timezone.utc


def at(*args) -> datetime:
    return datetime(*args, tzinfo=UTC)


# ── Slots ────────────────────────────────────────────────────────────────────


def test_daily_cron_slot_is_todays_run_once_it_is_due():
    cron = crontab(hour=8, minute=0)
    assert previous_cron_time(cron, at(2026, 11, 1, 8, 0, 30)) == at(2026, 11, 1, 8, 0)
    assert previous_cron_time(cron, at(2026, 11, 1, 14, 0)) == at(2026, 11, 1, 8, 0)
    assert previous_cron_time(cron, at(2026, 11, 1, 7, 59)) == at(2026, 10, 31, 8, 0)


def test_weekly_and_monthly_cron_slots():
    sunday = crontab(hour=3, minute=15, day_of_week=0)
    # 2026-11-01 is a Sunday.
    assert previous_cron_time(sunday, at(2026, 11, 4, 12, 0)) == at(2026, 11, 1, 3, 15)
    monthly = crontab(hour=3, minute=30, day_of_month=1)
    assert previous_cron_time(monthly, at(2026, 11, 20, 0, 0)) == at(2026, 11, 1, 3, 30)
    assert previous_cron_time(monthly, at(2026, 11, 1, 3, 29)) == at(2026, 10, 1, 3, 30)


def test_every_five_minutes_slot():
    cron = crontab(minute="*/5")
    assert previous_cron_time(cron, at(2026, 11, 1, 10, 7, 59)) == at(
        2026, 11, 1, 10, 5
    )


def test_two_beats_get_the_same_slot_and_a_catch_up_too():
    cron = crontab(hour=8, minute=0)
    on_time, _ = slot_for(cron, at(2026, 11, 1, 8, 0, 1))
    other_beat, _ = slot_for(cron, at(2026, 11, 1, 8, 0, 2))
    catch_up, ttl = slot_for(cron, at(2026, 11, 1, 13, 0))  # restarted beat
    assert on_time == other_beat == catch_up == "2026-11-01T08:00"
    assert ttl >= 2 * 86400


def test_interval_slots_change_every_interval():
    every = schedule(timedelta(seconds=60))
    a, ttl = slot_for(every, at(2026, 11, 1, 10, 0, 10))
    b, _ = slot_for(every, at(2026, 11, 1, 10, 0, 50))
    c, _ = slot_for(every, at(2026, 11, 1, 10, 1, 10))
    assert a == b != c
    assert ttl > 60


# ── Claims ───────────────────────────────────────────────────────────────────


class FakeRedis:
    def __init__(self):
        self.keys = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.keys:
            return None
        self.keys[key] = value
        return True


def test_claim_slot_once_per_slot():
    r = FakeRedis()
    assert claim_slot(r, "backup-daily", "2026-11-01T03:00", 60)
    assert not claim_slot(r, "backup-daily", "2026-11-01T03:00", 60)
    assert claim_slot(r, "backup-daily", "2026-11-02T03:00", 60)


def test_claim_slot_without_redis_sends():
    assert claim_slot(None, "x", "s", 60)

    broken = MagicMock()
    broken.set.side_effect = ConnectionError("down")
    assert claim_slot(broken, "x", "s", 60)


def _scheduler(app_celery, redis):
    sched = HubraScheduler.__new__(HubraScheduler)
    sched.app = app_celery
    sched._slot_client, sched._slot_client_ready = redis, True
    sched._tasks_since_sync = 0
    sched.sync_every_tasks = None
    sched.sync_every = None
    sched._last_sync = None
    sched.should_sync = lambda: False
    return sched


def test_second_beat_skips_a_slot_the_first_sent(app):
    from celery.beat import ScheduleEntry

    from hubra.core.tasks import celery_app
    from hubra.core.tasks.smoke import add  # noqa: F401 (registers the task)

    redis = FakeRedis()
    entry = ScheduleEntry(
        name="backup-daily",
        task="hubra.core.tasks.smoke.add",
        schedule=crontab(hour=3, minute=0),
        args=(1, 2),
        app=celery_app,
    )
    sent = []
    with patch.object(
        celery_app.tasks["hubra.core.tasks.smoke.add"],
        "apply_async",
        side_effect=lambda *a, **kw: sent.append(kw) or "sent",
    ):
        first, second = _scheduler(celery_app, redis), _scheduler(celery_app, redis)
        assert first.apply_async(entry, advance=False) == "sent"
        assert second.apply_async(entry, advance=False) is None
    assert len(sent) == 1
    assert sent[0]["headers"][HEADER] == "backup-daily"
    assert HEADER not in (entry.options.get("headers") or {})


# ── Worker lock ──────────────────────────────────────────────────────────────


def test_hand_started_tasks_never_take_the_job_lock(app):
    from hubra.core.tasks.smoke import add

    with patch.object(scheduling, "run_exclusive") as lock:
        assert add.apply(args=(1, 2)).get() == 3
    lock.assert_not_called()


def test_beat_sent_tasks_run_under_the_job_lock(app):
    from hubra.core.tasks.smoke import add

    with patch.object(
        scheduling, "run_exclusive", side_effect=lambda name, fn, *a, **kw: fn(*a, **kw)
    ) as lock:
        assert add.apply(args=(2, 3), headers={HEADER: "smoke"}).get() == 5
    assert lock.call_args.args[0] == "smoke"


def test_lock_keys_are_stable_and_distinct():
    assert scheduling.lock_key("backup-daily") == scheduling.lock_key("backup-daily")
    assert scheduling.lock_key("backup-daily") != scheduling.lock_key("backup-weekly")
    assert -(2**63) <= scheduling.lock_key("x") < 2**63


def test_overlapping_run_is_skipped_on_postgres(app):
    from hubra.core.extensions import db

    if db.engine.dialect.name != "postgresql":
        pytest.skip("advisory locks need Postgres")

    inside, release = threading.Event(), threading.Event()
    results = {}

    def slow():
        inside.set()
        release.wait(10)
        return "done"

    def first():
        with app.app_context():
            results["first"] = scheduling.run_exclusive("test-job", slow)

    t = threading.Thread(target=first)
    t.start()
    assert inside.wait(10)
    try:
        results["second"] = scheduling.run_exclusive("test-job", lambda: "ran")
    finally:
        release.set()
        t.join(10)
    assert results["first"] == "done"
    assert results["second"]["skipped"] == "already running"
    # Released afterwards: the next run goes ahead.
    assert scheduling.run_exclusive("test-job", lambda: "ran") == "ran"


def test_without_postgres_the_job_just_runs(app):
    from hubra.core.extensions import db

    if db.engine.dialect.name == "postgresql":
        pytest.skip("SQLite path")
    assert scheduling.run_exclusive("test-job", lambda: "ran") == "ran"
