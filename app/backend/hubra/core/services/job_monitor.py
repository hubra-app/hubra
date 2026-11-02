"""Background jobs at a glance: queued, running, failed and retried Celery tasks.

Shown in manage › Diagnose › Hintergrundjobs.  Celery's signals feed it
(``hubra.core.tasks.job_signals``):

* ``before_task_publish`` counts a job as **sent**,
* ``task_prerun`` / ``task_postrun`` keep the list of **running** jobs and
  count **done** jobs and their run time,
* ``task_retry`` counts a **retry** (the task asked Celery to run it again),
* ``task_failure`` counts a **failure** and keeps the failed job (name,
  arguments, club, error, the end of the traceback) so a platform admin
  can **run it again** with one click.

**Queued** is read from the broker: the length of Celery's Redis list and
the jobs workers took but have not started yet (``unacked``, e.g. ones
with a countdown).

Counters live in Redis in one hash per hour (kept for 48 hours) like the
performance counters; without Redis (tests, an outage) they live in this
process.  Failed jobs are kept for 7 days, at most ``MAX_FAILED``.

Privacy: the arguments of a failed job are stored so it can be run again,
and shown to platform admins with long strings shortened and values of
keys that look secret (``password``, ``token``, ``html`` …) hidden.
Recording never raises: a monitoring problem must not fail a job.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import traceback as tb
import uuid
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

KEEP_HOURS = 48
FAILED_KEEP_SECONDS = 7 * 24 * 3600
MAX_FAILED = 300
# A job still "running" after this long has died with its worker.
RUNNING_STALE_SECONDS = 3 * 3600
QUEUE = "celery"

_P = "hubra:jobs"
_FAILED = f"{_P}:failed"  # hash id -> json
_FAILED_ORDER = f"{_P}:failed:order"  # zset id -> time
_RUNNING = f"{_P}:running"  # hash task_id -> json
_SEP = "\t"
_SECRET_HINTS = (
    "password",
    "secret",
    "token",
    "key",
    "html",
    "body",
    "content",
    "code",
)
_ARG_TEXT_MAX = 120
_STORE_MAX = 16_000  # bytes of JSON arguments kept for a retry

COUNTERS = ("sent", "done", "failed", "retried")

_local: dict[str, dict] = {"hours": {}, "failed": {}, "running": {}}
_local_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hour_key(dt: datetime) -> str:
    return f"{_P}:h:{dt.strftime('%Y%m%d%H')}"


def _ctx():
    """An app context for signal handlers that Celery calls outside one."""
    from flask import has_app_context

    if has_app_context():
        return nullcontext()
    try:
        from hubra.core.tasks import celery_app

        return celery_app.flask_app.app_context()
    except Exception:  # noqa: BLE001
        return nullcontext()


def _redis():
    try:
        from flask import has_app_context

        if not has_app_context():
            return None
        from hubra.core.redis_client import get_redis_client

        return get_redis_client()
    except Exception:  # noqa: BLE001
        return None


_readers: dict[str, object] = {}


def _reader():
    """A client for the dashboard's reads: a longer timeout and no shared
    circuit breaker, so a hiccup elsewhere does not blank the page."""
    try:
        from flask import current_app

        url = current_app.config.get("REDIS_URL", "")
        if not url or url == "memory://":
            return None
        client = _readers.get(url)
        if client is None:
            import redis as redis_lib

            client = redis_lib.from_url(url, socket_connect_timeout=2, socket_timeout=2)
            _readers[url] = client
        return client
    except Exception:  # noqa: BLE001
        return None


def _redis_failed() -> None:
    try:
        from hubra.core.redis_client import mark_redis_down

        mark_redis_down()
    except Exception:  # noqa: BLE001
        pass


def _text(v) -> str:
    return v.decode() if isinstance(v, bytes) else str(v)


# ── Recording (called from the Celery signals) ───────────────────────────────


def count(task: str, what: str, ms: float | None = None) -> None:
    """Add one *what* (sent, done, failed, retried) for *task* this hour."""
    fields = {f"{task}{_SEP}{what}": 1}
    if ms is not None:
        fields[f"{task}{_SEP}ms"] = int(ms)
    try:
        with _ctx():
            key = _hour_key(_now())
            client = _redis()
            if client is not None:
                try:
                    pipe = client.pipeline(transaction=False)
                    for f, n in fields.items():
                        pipe.hincrby(key, f, n)
                    pipe.expire(key, KEEP_HOURS * 3600)
                    pipe.execute()
                    return
                except Exception:  # noqa: BLE001
                    _redis_failed()
            with _local_lock:
                h = _local["hours"].setdefault(key, {})
                for f, n in fields.items():
                    h[f] = h.get(f, 0) + n
    except Exception:  # noqa: BLE001
        logger.debug("job counter not written", exc_info=True)


def started(task_id: str, task: str, tenant_id=None) -> None:
    item = json.dumps(
        {"id": task_id, "task": task, "tenant_id": tenant_id, "started": time.time()}
    )
    try:
        with _ctx():
            client = _redis()
            if client is not None:
                try:
                    client.hset(_RUNNING, task_id, item)
                    return
                except Exception:  # noqa: BLE001
                    _redis_failed()
            with _local_lock:
                _local["running"][task_id] = item
    except Exception:  # noqa: BLE001
        logger.debug("running job not written", exc_info=True)


def finished(task_id: str) -> float | None:
    """Forget a running job; its run time in ms, if it was known."""
    try:
        with _ctx():
            client = _redis()
            raw = None
            if client is not None:
                try:
                    pipe = client.pipeline(transaction=False)
                    pipe.hget(_RUNNING, task_id)
                    pipe.hdel(_RUNNING, task_id)
                    raw = pipe.execute()[0]
                except Exception:  # noqa: BLE001
                    _redis_failed()
                    client = None
            if client is None:
                with _local_lock:
                    raw = _local["running"].pop(task_id, None)
            if raw:
                return (time.time() - json.loads(_text(raw))["started"]) * 1000
    except Exception:  # noqa: BLE001
        logger.debug("running job not removed", exc_info=True)
    return None


def _safe_json(value):
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return repr(value)


def failed(
    *,
    task_id: str,
    task: str,
    args,
    kwargs,
    exception: BaseException | None,
    einfo=None,
    tenant_id=None,
    retries: int = 0,
) -> None:
    """Keep a failed job so it can be looked at and run again."""
    try:
        trace = ""
        if einfo is not None:
            trace = str(getattr(einfo, "traceback", "") or "")
        elif exception is not None:
            trace = "".join(tb.format_exception(exception))
        payload = {
            "args": _safe_json(list(args or [])),
            "kwargs": _safe_json(dict(kwargs or {})),
        }
        replayable = len(json.dumps(payload)) <= _STORE_MAX
        entry = {
            "id": uuid.uuid4().hex[:16],
            "task_id": task_id,
            "task": task,
            "time": _now().isoformat(),
            "tenant_id": int(tenant_id) if str(tenant_id or "").isdigit() else None,
            "error": f"{type(exception).__name__}: {exception}"[:1000]
            if exception
            else "",
            "traceback": "\n".join(trace.strip().splitlines()[-12:])[:4000],
            "retries": int(retries or 0),
            "payload": payload if replayable else None,
            "retried_at": None,
            "retried_by": None,
            "retry_task_id": None,
        }
        _save_failure(entry)
    except Exception:  # noqa: BLE001
        logger.debug("failed job not recorded", exc_info=True)


def _save_failure(entry: dict) -> None:
    with _ctx():
        client = _redis()
        raw = json.dumps(entry)
        if client is not None:
            try:
                pipe = client.pipeline(transaction=False)
                pipe.hset(_FAILED, entry["id"], raw)
                pipe.zadd(_FAILED_ORDER, {entry["id"]: time.time()})
                pipe.execute()
                _prune(client)
                return
            except Exception:  # noqa: BLE001
                _redis_failed()
        with _local_lock:
            _local["failed"][entry["id"]] = raw
            if len(_local["failed"]) > MAX_FAILED:
                for old in list(_local["failed"])[: len(_local["failed"]) - MAX_FAILED]:
                    _local["failed"].pop(old, None)


def _prune(client) -> None:
    cutoff = time.time() - FAILED_KEEP_SECONDS
    old = client.zrangebyscore(_FAILED_ORDER, 0, cutoff)
    extra = client.zcard(_FAILED_ORDER) - MAX_FAILED
    if extra > 0:
        old = list(old) + list(client.zrange(_FAILED_ORDER, 0, extra - 1))
    if old:
        client.hdel(_FAILED, *old)
        client.zrem(_FAILED_ORDER, *old)


# ── Reading ──────────────────────────────────────────────────────────────────


def _hours(hours: int) -> list[dict]:
    now = _now()
    keys = [_hour_key(now - timedelta(hours=i)) for i in range(hours)]
    client = _reader()
    if client is not None:
        try:
            pipe = client.pipeline(transaction=False)
            for k in keys:
                pipe.hgetall(k)
            return [
                {_text(a): int(b) for a, b in (h or {}).items()} for h in pipe.execute()
            ]
        except Exception:  # noqa: BLE001
            _redis_failed()
    with _local_lock:
        return [dict(_local["hours"].get(k, {})) for k in keys]


def queue_depth() -> dict:
    """Jobs waiting in the broker, and taken by a worker but not started."""
    client = _reader()
    if client is None:
        return {"queued": None, "reserved": None}
    try:
        pipe = client.pipeline(transaction=False)
        pipe.llen(QUEUE)
        pipe.hlen("unacked")
        queued, reserved = pipe.execute()
        return {"queued": int(queued), "reserved": int(reserved)}
    except Exception:  # noqa: BLE001
        _redis_failed()
        return {"queued": None, "reserved": None}


def running() -> list[dict]:
    client = _reader()
    rows: list[str] = []
    if client is not None:
        try:
            rows = [_text(v) for v in client.hvals(_RUNNING)]
        except Exception:  # noqa: BLE001
            _redis_failed()
            client = None
    if client is None:
        with _local_lock:
            rows = list(_local["running"].values())
    now = time.time()
    out, stale = [], []
    for raw in rows:
        item = json.loads(raw)
        if now - item["started"] > RUNNING_STALE_SECONDS:
            stale.append(item["id"])
            continue
        item["seconds"] = int(now - item["started"])
        item["started"] = datetime.fromtimestamp(
            item["started"], timezone.utc
        ).isoformat()
        out.append(item)
    if stale and client is not None:
        try:
            client.hdel(_RUNNING, *stale)
        except Exception:  # noqa: BLE001
            pass
    return sorted(out, key=lambda r: -r["seconds"])


def failures() -> list[dict]:
    client = _reader()
    if client is not None:
        try:
            ids = client.zrevrange(_FAILED_ORDER, 0, MAX_FAILED - 1)
            raws = client.hmget(_FAILED, ids) if ids else []
            return [json.loads(_text(r)) for r in raws if r]
        except Exception:  # noqa: BLE001
            _redis_failed()
    with _local_lock:
        return [json.loads(r) for r in reversed(list(_local["failed"].values()))]


def get_failure(failure_id: str) -> dict | None:
    client = _reader()
    if client is not None:
        try:
            raw = client.hget(_FAILED, failure_id)
            return json.loads(_text(raw)) if raw else None
        except Exception:  # noqa: BLE001
            _redis_failed()
    with _local_lock:
        raw = _local["failed"].get(failure_id)
    return json.loads(raw) if raw else None


def update_failure(entry: dict) -> None:
    client = _reader()
    if client is not None:
        try:
            client.hset(_FAILED, entry["id"], json.dumps(entry))
            return
        except Exception:  # noqa: BLE001
            _redis_failed()
    with _local_lock:
        _local["failed"][entry["id"]] = json.dumps(entry)


def remove_failure(failure_id: str) -> bool:
    client = _reader()
    if client is not None:
        try:
            pipe = client.pipeline(transaction=False)
            pipe.hdel(_FAILED, failure_id)
            pipe.zrem(_FAILED_ORDER, failure_id)
            return bool(pipe.execute()[0])
        except Exception:  # noqa: BLE001
            _redis_failed()
    with _local_lock:
        return _local["failed"].pop(failure_id, None) is not None


def _shown(value, key: str = ""):
    """An argument as platform admins see it: secrets hidden, text shortened."""
    if any(h in key.lower() for h in _SECRET_HINTS):
        return "•••"
    if isinstance(value, str):
        return value if len(value) <= _ARG_TEXT_MAX else value[:_ARG_TEXT_MAX] + "…"
    if isinstance(value, dict):
        return {k: _shown(v, str(k)) for k, v in list(value.items())[:20]}
    if isinstance(value, list):
        return [_shown(v) for v in value[:20]]
    return value


def failure_to_json(entry: dict, names: dict[int, str] | None = None) -> dict:
    payload = entry.get("payload")
    out = {k: v for k, v in entry.items() if k != "payload"}
    out["can_retry"] = payload is not None
    out["args"] = _shown(payload["args"]) if payload else None
    out["kwargs"] = _shown(payload["kwargs"]) if payload else None
    out["club"] = (names or {}).get(entry.get("tenant_id"))
    return out


def summary(hours: int = 24) -> dict:
    """Totals and per-task counts for the last *hours* clock hours."""
    hours = max(1, min(KEEP_HOURS, int(hours)))
    per_task: dict[str, dict] = {}
    series = []
    for h in reversed(_hours(hours)):
        bucket = dict.fromkeys(COUNTERS, 0)
        for field, n in h.items():
            task, _, what = field.rpartition(_SEP)
            row = per_task.setdefault(task, {**dict.fromkeys(COUNTERS, 0), "ms": 0})
            row[what] = row.get(what, 0) + n
            if what in bucket:
                bucket[what] += n
        series.append(bucket)
    tasks = []
    for name, row in per_task.items():
        ms = row.pop("ms", 0)
        row["avg_ms"] = int(ms / row["done"]) if row["done"] else None
        tasks.append({"task": name, **row})
    tasks.sort(key=lambda r: (-r["failed"], -r["sent"], r["task"]))
    totals = {c: sum(r[c] for r in tasks) for c in COUNTERS}
    return {"hours": hours, "totals": totals, "tasks": tasks, "series": series}


# ── Retry ────────────────────────────────────────────────────────────────────


class RetryError(Exception):
    pass


def retry(failure_id: str, by: str) -> dict:
    """Send a failed job again with the same arguments and club."""
    from hubra.core.tasks import celery_app

    entry = get_failure(failure_id)
    if entry is None:
        raise RetryError("not_found")
    if entry.get("payload") is None:
        raise RetryError("not_replayable")
    celery_app.loader.import_default_modules()
    if entry["task"] not in celery_app.tasks:
        raise RetryError("unknown_task")
    headers = {"tenant_id": entry["tenant_id"]} if entry.get("tenant_id") else None
    result = celery_app.send_task(
        entry["task"],
        args=entry["payload"]["args"],
        kwargs=entry["payload"]["kwargs"],
        headers=headers,
    )
    entry["retried_at"] = _now().isoformat()
    entry["retried_by"] = by
    entry["retry_task_id"] = getattr(result, "id", None)
    update_failure(entry)
    return entry


def reset_local() -> None:
    """Tests: forget what this process recorded."""
    with _local_lock:
        for v in _local.values():
            v.clear()
