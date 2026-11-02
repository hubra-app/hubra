"""Scheduled jobs that stay single when Hubra runs more than one process.

Two guards, both no-ops for a plain one-of-everything install:

1. **One send per schedule slot** (beat side).  :class:`HubraScheduler`
   claims ``hubra:beat:<entry>:<slot>`` in Redis before it sends a due
   task.  A second beat, or a beat that restarted with an old schedule
   file and wants to catch up, finds the slot taken and skips it.  The
   slot is the time the entry was due (the last cron time, or the start
   of the current interval), so every beat computes the same one.

2. **One run at a time** (worker side).  A task sent by beat carries the
   entry name in the ``hubra_schedule`` header.  The worker takes a
   Postgres advisory lock named after the entry for the length of the
   run; if another worker (or another process of the same worker) still
   runs it, this run is skipped instead of overlapping.

Both fail open: without Redis the slot claim is skipped (one beat is
still one send), and without Postgres the task runs without the lock.
Tasks started by hand (``.delay()`` from a request or the CLI) carry no
header and are never skipped.
"""

from __future__ import annotations

import copy
import hashlib
import logging
from datetime import datetime, timedelta

from celery.beat import PersistentScheduler
from celery.schedules import crontab, schedule as interval_schedule

_log = logging.getLogger(__name__)

HEADER = "hubra_schedule"
_KEY_PREFIX = "hubra:beat"
_LOCK_NAMESPACE = "hubra-job:"


# ── Schedule slots ───────────────────────────────────────────────────────────


def _dow(day) -> int:
    """Celery's day of week: 0 = Sunday."""
    return (day.weekday() + 1) % 7


def previous_cron_time(cron: crontab, now: datetime) -> datetime | None:
    """The latest time at or before *now* that *cron* fires (minute precision).

    Looks back up to 400 days, which covers every crontab Hubra uses
    (the rarest is monthly).  Celery fires only on days that match both
    ``day_of_month`` and ``day_of_week``, so this does the same.
    """
    now = now.replace(second=0, microsecond=0)
    hours = sorted(cron.hour, reverse=True)
    minutes = sorted(cron.minute, reverse=True)
    for back in range(400):
        day = (now - timedelta(days=back)).date()
        if (
            day.month not in cron.month_of_year
            or day.day not in cron.day_of_month
            or _dow(day) not in cron.day_of_week
        ):
            continue
        for hour in hours:
            for minute in minutes:
                at = now.replace(
                    year=day.year,
                    month=day.month,
                    day=day.day,
                    hour=hour,
                    minute=minute,
                )
                if at <= now:
                    return at
    return None


def slot_for(sched, now: datetime) -> tuple[str, int]:
    """``(slot, ttl_seconds)`` for the run of *sched* that is due at *now*.

    Every beat process computes the same slot for the same run, so the
    slot names the run.  The TTL keeps the claim until well after the
    next run, so a late catch-up of this run still finds it.
    """
    if isinstance(sched, crontab):
        at = previous_cron_time(sched, now)
        if at is not None:
            before = previous_cron_time(sched, at - timedelta(minutes=1))
            gap = (at - before).total_seconds() if before else 86400
            return at.strftime("%Y-%m-%dT%H:%M"), int(2 * gap + 3600)
    if isinstance(sched, interval_schedule):
        seconds = max(1, int(sched.run_every.total_seconds()))
        bucket = int(now.timestamp()) // seconds
        return f"every{seconds}s-{bucket}", 2 * seconds + 60
    # Anything else (solar, custom): one claim per minute.
    return now.strftime("%Y-%m-%dT%H:%M"), 3600


# ── Beat side ────────────────────────────────────────────────────────────────


def _beat_redis(app):
    """A Redis client for slot claims, or None (tests, no Redis)."""
    flask_app = getattr(app, "flask_app", None)
    url = (flask_app.config.get("REDIS_URL") if flask_app else None) or ""
    if not url or url.startswith("memory"):
        return None
    try:
        import redis as redis_lib

        return redis_lib.from_url(url, socket_connect_timeout=2, socket_timeout=2)
    except Exception:
        _log.warning("beat: no Redis client for schedule slots", exc_info=True)
        return None


def claim_slot(client, name: str, slot: str, ttl: int) -> bool:
    """True if this process may send *name* for *slot*.

    Without Redis, or when Redis errors, it says yes: a single beat then
    behaves exactly as before.
    """
    if client is None:
        return True
    try:
        return bool(client.set(f"{_KEY_PREFIX}:{name}:{slot}", "1", nx=True, ex=ttl))
    except Exception:
        _log.warning("beat: Redis unavailable, sending %s without a slot claim", name)
        return True


class HubraScheduler(PersistentScheduler):
    """Celery beat's file scheduler, plus a Redis claim per schedule slot."""

    _slot_client = None
    _slot_client_ready = False

    def _redis(self):
        if not self._slot_client_ready:
            self._slot_client = _beat_redis(self.app)
            self._slot_client_ready = True
        return self._slot_client

    def apply_async(self, entry, producer=None, advance=True, **kwargs):
        if advance:
            entry = self.reserve(entry)
        slot, ttl = slot_for(entry.schedule, entry.schedule.now())
        if not claim_slot(self._redis(), entry.name, slot, ttl):
            _log.info(
                "beat: %s for %s was already sent by another scheduler; skipping",
                entry.name,
                slot,
            )
            return None
        # Celery sends entry.options as the task options; add the header on
        # a copy so it never lands in the schedule file.
        tagged = copy.copy(entry)
        options = dict(entry.options or {})
        options["headers"] = {**(options.get("headers") or {}), HEADER: entry.name}
        tagged.options = options
        return super().apply_async(tagged, producer=producer, advance=False, **kwargs)


# ── Worker side ──────────────────────────────────────────────────────────────


def lock_key(name: str) -> int:
    """A stable signed 64-bit advisory lock key for job *name*."""
    digest = hashlib.blake2b((_LOCK_NAMESPACE + name).encode(), digest_size=8)
    return int.from_bytes(digest.digest(), "big", signed=True)


def run_exclusive(name: str, fn, *args, **kwargs):
    """Run *fn* unless another process holds job *name*'s lock.

    The lock is a session-level ``pg_try_advisory_lock`` on a connection
    of its own, so the task can commit as often as it likes; Postgres
    drops the lock if the worker dies.  Returns ``{"skipped": ...}`` when
    the job is already running elsewhere.
    """
    from sqlalchemy import text

    from hubra.core.extensions import db

    engine = db.engine
    if engine.dialect.name != "postgresql":
        return fn(*args, **kwargs)

    key = lock_key(name)
    try:
        conn = engine.connect()
    except Exception:
        _log.warning("job %s: no database connection for the lock", name)
        return fn(*args, **kwargs)
    try:
        got = conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": key}).scalar()
        conn.commit()
        if not got:
            _log.info("job %s is still running elsewhere; skipping this run", name)
            return {"skipped": "already running", "job": name}
        try:
            return fn(*args, **kwargs)
        finally:
            try:
                conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})
                conn.commit()
            except Exception:  # closing the connection releases it anyway
                _log.debug("job %s: unlock failed", name, exc_info=True)
    finally:
        conn.close()
