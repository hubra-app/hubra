"""Server performance monitoring: API request timing and slow database queries.

* Every API request is timed (``install``): per route and method it counts
  requests, status classes (2xx to 5xx), requests slower than the platform
  setting ``perf.slow_request_ms``, the time spent in the database and a
  histogram of durations, from which p50 and p95 are read.
* Every SQL statement is timed (an engine listener).  One that takes longer
  than ``perf.slow_query_ms`` is counted under its fingerprint and written
  to the log.
* ``summary`` reads it back for manage › Diagnostics › Performance;
  ``problems`` adds an open problem when the API's p95 over the last hour is
  above ``perf.p95_warning_ms`` or many requests failed with a server error.

Privacy: a route is the URL rule (``/api/v1/members/<int:member_id>``), never
the path, query string, body, headers, user or club.  A query is stored and
logged as its normalized text: bound parameters are never read, and string
and number literals in the text become ``?``.

Counters live in Redis in one hash per hour, kept for 26 hours, so every
worker and replica adds to the same numbers.  Without Redis (tests, an
outage) they live in this process only.  Recording must never slow down or
fail a request: every write is caught.
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
from datetime import datetime, timedelta, timezone

from flask import Flask, g, has_app_context, has_request_context, request

logger = logging.getLogger(__name__)

# Upper bounds (ms) of the duration buckets; the last bucket is open.
BUCKETS = (
    5, 10, 20, 35, 50, 75, 100, 150, 200, 300, 500, 750,
    1000, 1500, 2000, 3000, 5000, 10000,
)  # fmt: skip

# Defaults of the platform settings perf.*.
SLOW_REQUEST_MS = 1000
SLOW_QUERY_MS = 250
P95_WARNING_MS = 1500
# An hour needs this many requests before its p95 counts as a problem.
MIN_REQUESTS = 50
# Share of 5xx answers in the last hour that is an open problem.
SERVER_ERROR_SHARE = 0.05
MIN_REQUESTS_FOR_ERRORS = 20
# Server errors in a process's first seconds (a release starting up, its
# database pool and caches warming) are counted apart, as "w5", so a rollout
# does not look like an outage.  A release that keeps failing counts after.
WARMUP_SECONDS = 120
_process_started = time.monotonic()

_KEEP_HOURS = 26
_SETTINGS_TTL = 60.0  # seconds a process trusts its copy of the thresholds
_SKIP_PREFIXES = ("/health", "/api/v1/global/health", "/static")
_SKIP_METHODS = {"OPTIONS", "HEAD"}
_SEP = "\t"
_SQL_TEXT_MAX = 400

# The thresholds this process uses.  The SQL listener runs inside a query
# and must not read the database, so it only ever reads this copy; it is
# refreshed between requests and before each Celery task.
_thresholds = {
    "slow_request_ms": SLOW_REQUEST_MS,
    "slow_query_ms": SLOW_QUERY_MS,
    "p95_warning_ms": P95_WARNING_MS,
}
_thresholds_at = 0.0
_refreshing = False

# Per-process store when Redis is unavailable: {key: {field: value}}.
_local: dict[str, dict[str, float | str]] = {}
_local_lock = threading.Lock()


# ── Thresholds ────────────────────────────────────────────────────────────────


def thresholds() -> dict[str, int]:
    return dict(_thresholds)


def refresh_thresholds(force: bool = False) -> None:
    """Read the perf.* platform settings, at most once a minute per process."""
    global _thresholds_at, _refreshing
    if _refreshing or (not force and time.monotonic() - _thresholds_at < _SETTINGS_TTL):
        return
    _refreshing = True
    try:
        from hubra.core.services import platform_settings

        for name in _thresholds:
            try:
                _thresholds[name] = int(platform_settings.get(f"perf.{name}"))
            except ValueError:
                pass
    except Exception:  # noqa: BLE001 - keep the last values
        logger.debug("perf thresholds not refreshed", exc_info=True)
        try:
            # A failed read must not leave the request's transaction aborted.
            from hubra.core.extensions import db

            db.session.rollback()
        except Exception:  # noqa: BLE001
            pass
    finally:
        _thresholds_at = time.monotonic()
        _refreshing = False


# ── Store ─────────────────────────────────────────────────────────────────────


def _redis():
    try:
        from hubra.core.redis_client import get_redis_client

        return get_redis_client()
    except Exception:  # noqa: BLE001
        return None


def _redis_failed() -> None:
    from hubra.core.redis_client import mark_redis_down

    mark_redis_down()


def _hour(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H")


def _key(kind: str, dt: datetime) -> str:
    return f"perf:{kind}:{_hour(dt)}"


def _slot(dt: datetime) -> str:
    """Ten-minute slot, for the last-hour totals."""
    return f"perf:tot:{_hour(dt)}{dt.minute // 10}"


def _incr(writes: dict[str, dict[str, int]], maxes: dict[str, int] | None = None,
          texts: dict[str, str] | None = None) -> None:  # fmt: skip
    """Add the counts in *writes* (``{key: {field: n}}``); raise *maxes* and
    set *texts* in the first key."""
    first = next(iter(writes))
    client = _redis()
    if client is not None:
        try:
            pipe = client.pipeline(transaction=False)
            for key, fields in writes.items():
                for f, n in fields.items():
                    pipe.hincrby(key, f, int(n))
                pipe.expire(key, _KEEP_HOURS * 3600)
            for f, v in (texts or {}).items():
                pipe.hset(first, f, v)
            pipe.execute()
            if maxes:
                # Rare (slow queries only), so read-then-write is fine.
                current = client.hmget(first, list(maxes))
                higher = {
                    f: v
                    for (f, v), old in zip(maxes.items(), current)
                    if old is None or int(old) < v
                }
                if higher:
                    client.hset(first, mapping=higher)
            return
        except Exception:  # noqa: BLE001
            _redis_failed()
            logger.debug("perf counters not written to Redis", exc_info=True)
    with _local_lock:
        for key, fields in writes.items():
            h = _local.setdefault(key, {})
            for f, n in fields.items():
                h[f] = float(h.get(f, 0)) + n
        h = _local[first]
        for f, v in (maxes or {}).items():
            if float(h.get(f, 0)) < v:
                h[f] = v
        for f, v in (texts or {}).items():
            h[f] = v
        if len(_local) > 400:
            for old in sorted(_local)[: len(_local) - 300]:
                _local.pop(old, None)


def _read(keys: list[str]) -> tuple[list[dict[str, str]], str]:
    """The hashes *keys* and where they came from ("redis" or "memory")."""
    client = _redis()
    if client is not None:
        try:
            pipe = client.pipeline(transaction=False)
            for k in keys:
                pipe.hgetall(k)
            out = []
            for h in pipe.execute():
                out.append(
                    {
                        (a.decode() if isinstance(a, bytes) else a): (
                            b.decode() if isinstance(b, bytes) else b
                        )
                        for a, b in (h or {}).items()
                    }
                )
            return out, "redis"
        except Exception:  # noqa: BLE001
            _redis_failed()
    with _local_lock:
        return [
            {f: str(v) for f, v in _local.get(k, {}).items()} for k in keys
        ], "memory"


def reset_local() -> None:
    """Forget the per-process counters (tests)."""
    global _thresholds_at
    with _local_lock:
        _local.clear()
    _thresholds_at = 0.0


# ── Requests ──────────────────────────────────────────────────────────────────


def _bucket(ms: float) -> int:
    for i, upper in enumerate(BUCKETS):
        if ms <= upper:
            return i
    return len(BUCKETS)


def route_label() -> str:
    """``"GET /api/v1/members/<int:member_id>"``: the rule, never the path."""
    rule = request.url_rule
    return f"{request.method} {rule.rule if rule is not None else '(no route)'}"


def record_request(route: str, status: int, ms: float, db_ms: float = 0.0,
                   queries: int = 0, at: datetime | None = None) -> None:  # fmt: skip
    """Count one request.  *route* is a label from ``route_label``."""
    p = route + _SEP
    status_class = min(5, max(1, status // 100))
    warming = status_class == 5 and time.monotonic() - _process_started < WARMUP_SECONDS
    fields = {
        p + "n": 1,
        p + "ms": int(ms),
        p + f"b{_bucket(ms)}": 1,
        p + ("w5" if warming else f"s{status_class}"): 1,
    }
    if db_ms:
        fields[p + "db"] = int(db_ms)
    if queries:
        fields[p + "q"] = queries
    slow = _thresholds["slow_request_ms"]
    if slow and ms >= slow:
        fields[p + "slow"] = 1
    at = at or datetime.now(timezone.utc)
    total = {
        k.rpartition(_SEP)[2]: v
        for k, v in fields.items()
        if k.rpartition(_SEP)[2][0] in "bsn"
    }
    _incr({_key("req", at): fields, _slot(at): total})


def install(app: Flask) -> None:
    """Time every API request.  Register before the other request hooks so
    the time includes them (after_request hooks run in reverse)."""

    @app.before_request
    def _perf_start() -> None:
        if request.method in _SKIP_METHODS or request.path.startswith(_SKIP_PREFIXES):
            return
        refresh_thresholds()
        g._perf_start = time.monotonic()
        g._perf_db_ms = 0.0
        g._perf_queries = 0

    @app.after_request
    def _perf_end(response):
        start = g.pop("_perf_start", None)
        if start is None or g.get("maintenance"):
            # Maintenance answers are planned 503s, not server errors.
            return response
        try:
            ms = (time.monotonic() - start) * 1000
            route = route_label()
            record_request(
                route,
                response.status_code,
                ms,
                g.get("_perf_db_ms", 0.0),
                g.get("_perf_queries", 0),
            )
            slow = _thresholds["slow_request_ms"]
            if slow and ms >= slow:
                logger.warning(
                    "slow request",
                    extra={
                        "perf": "slow_request",
                        "route": route,
                        "status": response.status_code,
                        "duration_ms": int(ms),
                        "db_ms": int(g.get("_perf_db_ms", 0.0)),
                        "queries": g.get("_perf_queries", 0),
                    },
                )
        except Exception:  # noqa: BLE001
            logger.debug("request timing not recorded", exc_info=True)
        return response


# ── Queries ───────────────────────────────────────────────────────────────────

_RE_STRING = re.compile(r"'(?:[^']|'')*'")
_RE_PARAM_LIST = re.compile(r"(?:%\([^)]*\)s|\?)(?:\s*,\s*(?:%\([^)]*\)s|\?))+")
_RE_PARAM = re.compile(r"%\([^)]*\)s|%s|\$\d+")
_RE_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])")
_RE_SPACE = re.compile(r"\s+")


def normalize_sql(statement: str) -> str:
    """The statement with every literal and parameter as ``?``, on one line."""
    s = _RE_STRING.sub("?", statement)
    s = _RE_PARAM.sub("?", s)
    s = _RE_PARAM_LIST.sub("?, …", s)
    s = _RE_NUMBER.sub("?", s)
    s = _RE_SPACE.sub(" ", s).strip()
    return s[:_SQL_TEXT_MAX] + ("…" if len(s) > _SQL_TEXT_MAX else "")


def _fingerprint(text: str) -> str:
    return hashlib.sha1(text.encode(), usedforsecurity=False).hexdigest()[:12]


def _where() -> str:
    if has_request_context():
        try:
            return route_label()
        except Exception:  # noqa: BLE001
            return "request"
    try:
        from celery import current_task

        if current_task and current_task.name:
            return f"task {current_task.name}"
    except Exception:  # noqa: BLE001
        pass
    return "other"


def record_query(statement: str, ms: float, at: datetime | None = None) -> str:
    """Count one slow query; returns its fingerprint."""
    text = normalize_sql(statement)
    fp = _fingerprint(text)
    p = fp + _SEP
    _incr(
        {
            _key("sql", at or datetime.now(timezone.utc)): {
                p + "n": 1,
                p + "ms": int(ms),
            }
        },
        maxes={p + "max": int(ms)},
        texts={p + "sql": text, p + "where": _where()},
    )
    return fp


def _before_cursor(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("_perf_t", []).append(time.monotonic())


def _after_cursor(conn, cursor, statement, parameters, context, executemany):
    stack = conn.info.get("_perf_t")
    if not stack:
        return
    ms = (time.monotonic() - stack.pop()) * 1000
    try:
        if has_app_context() and "_perf_start" in g:
            g._perf_db_ms = g.get("_perf_db_ms", 0.0) + ms
            g._perf_queries = g.get("_perf_queries", 0) + 1
        slow = _thresholds["slow_query_ms"]
        if not slow or ms < slow or _refreshing:
            return
        fp = record_query(statement, ms)
        logger.warning(
            "slow query",
            extra={
                "perf": "slow_query",
                "query_id": fp,
                "duration_ms": int(ms),
                "where": _where(),
                "sql": normalize_sql(statement),
            },
        )
    except Exception:  # noqa: BLE001
        logger.debug("query timing not recorded", exc_info=True)


def _error_cursor(context) -> None:
    stack = context.connection.info.get("_perf_t") if context.connection else None
    if stack:
        stack.pop()


def install_sql_listener() -> None:
    """Time every statement on every engine (once per process)."""
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    if not event.contains(Engine, "before_cursor_execute", _before_cursor):
        event.listen(Engine, "before_cursor_execute", _before_cursor)
        event.listen(Engine, "after_cursor_execute", _after_cursor)
        event.listen(Engine, "handle_error", _error_cursor)


# ── Reading back ──────────────────────────────────────────────────────────────


def percentile(buckets: list[int], q: float) -> int | None:
    """Estimate the *q* quantile (0..1) from bucket counts, in ms."""
    total = sum(buckets)
    if not total:
        return None
    rank = q * total
    seen = 0
    for i, n in enumerate(buckets):
        if n and seen + n >= rank:
            lower = BUCKETS[i - 1] if i else 0
            if i >= len(BUCKETS):
                return BUCKETS[-1]
            upper = BUCKETS[i]
            return int(round(lower + (upper - lower) * (rank - seen) / n))
        seen += n
    return BUCKETS[-1]


def _hours(hours: int, now: datetime) -> list[datetime]:
    return [now - timedelta(hours=h) for h in range(hours)]


def _routes(hashes: list[dict[str, str]]) -> dict[str, dict]:
    routes: dict[str, dict] = {}
    for h in hashes:
        for field, value in h.items():
            route, _, name = field.rpartition(_SEP)
            if not route:
                continue
            r = routes.setdefault(
                route,
                {"b": [0] * (len(BUCKETS) + 1), "s": [0] * 6},
            )
            n = int(float(value))
            if name.startswith("b") and name[1:].isdigit():
                r["b"][min(int(name[1:]), len(BUCKETS))] += n
            elif name.startswith("s") and name[1:].isdigit():
                r["s"][int(name[1:])] += n
            else:
                r[name] = r.get(name, 0) + n
    return routes


def _route_row(label: str, r: dict) -> dict:
    n = r.get("n", 0)
    method, _, rule = label.partition(" ")
    return {
        "route": rule,
        "method": method,
        "requests": n,
        "p50": percentile(r["b"], 0.5),
        "p95": percentile(r["b"], 0.95),
        "mean": round(r.get("ms", 0) / n) if n else None,
        "dbMean": round(r.get("db", 0) / n) if n else None,
        "queriesMean": round(r.get("q", 0) / n, 1) if n else None,
        "slow": r.get("slow", 0),
        "status": {f"{c}xx": r["s"][c] for c in range(1, 6) if r["s"][c]},
        "totalMs": r.get("ms", 0),
    }


def summary(hours: int = 24, now: datetime | None = None) -> dict:
    """Requests and slow queries of the last *hours* clock hours (1 to 24),
    the current one included: ``hours=2`` is since the start of the previous
    hour.  ``lastHour`` is the last 50 to 60 minutes."""
    hours = max(1, min(24, int(hours)))
    now = now or datetime.now(timezone.utc)
    slots = _hours(hours, now)
    req, source = _read([_key("req", t) for t in slots])
    sql, _ = _read([_key("sql", t) for t in slots])

    routes = _routes(req)
    total = {"b": [0] * (len(BUCKETS) + 1), "s": [0] * 6}
    for r in routes.values():
        total["b"] = [a + b for a, b in zip(total["b"], r["b"])]
        total["s"] = [a + b for a, b in zip(total["s"], r["s"])]
        for k in ("n", "ms", "db", "q", "slow"):
            total[k] = total.get(k, 0) + r.get(k, 0)
    rows = sorted(
        (_route_row(label, r) for label, r in routes.items()),
        key=lambda x: x["totalMs"],
        reverse=True,
    )
    overall = _route_row("ALL *", total)

    queries: dict[str, dict] = {}
    for h in sql:
        for field, value in h.items():
            fp, _, name = field.rpartition(_SEP)
            q = queries.setdefault(fp, {"n": 0, "ms": 0, "max": 0})
            if name in ("sql", "where"):
                q[name] = value
            elif name == "max":
                q["max"] = max(q["max"], int(float(value)))
            elif name in ("n", "ms"):
                q[name] += int(float(value))
    slow_queries = sorted(
        (
            {
                "id": fp,
                "sql": q.get("sql", ""),
                "where": q.get("where", ""),
                "count": q["n"],
                "meanMs": round(q["ms"] / q["n"]) if q["n"] else None,
                "maxMs": q["max"],
                "totalMs": q["ms"],
            }
            for fp, q in queries.items()
            if q["n"]
        ),
        key=lambda x: x["totalMs"],
        reverse=True,
    )

    return {
        "hours": hours,
        "source": source,
        "thresholds": thresholds(),
        "total": {k: overall[k] for k in overall if k not in ("route", "method")},
        "lastHour": last_hour(now),
        "routes": rows[:100],
        "routeCount": len(rows),
        "queries": slow_queries[:50],
    }


def last_hour(now: datetime | None = None) -> dict:
    """Totals of the last six ten-minute slots (50 to 60 minutes)."""
    now = now or datetime.now(timezone.utc)
    hashes, _ = _read([_slot(now - timedelta(minutes=10 * i)) for i in range(6)])
    total = {"b": [0] * (len(BUCKETS) + 1), "s": [0] * 6}
    for h in hashes:
        for name, value in h.items():
            n = int(float(value))
            if name[0] in "bs" and name[1:].isdigit():
                total[name[0]][min(int(name[1:]), len(total[name[0]]) - 1)] += n
            else:
                total[name] = total.get(name, 0) + n
    row = _route_row("ALL *", total)
    return {k: row[k] for k in ("requests", "p50", "p95", "slow", "status")}


def problems() -> list[dict]:
    """Open problems for the alerts overview: a slow API or many 5xx answers
    in the last hour."""
    out: list[dict] = []
    try:
        refresh_thresholds()
        last = last_hour()
    except Exception:  # noqa: BLE001
        logger.debug("perf summary failed", exc_info=True)
        return out
    n = last["requests"]
    limit = _thresholds["p95_warning_ms"]
    if limit and n >= MIN_REQUESTS and (last["p95"] or 0) > limit:
        out.append(
            {
                "id": "perf:slow",
                "level": "warning",
                "area": "performance",
                "title": f"API is slow: p95 {last['p95']} ms in the last hour",
                "detail": f"Above the warning limit of {limit} ms; "
                f"{n} requests, {last['slow']} slower than "
                f"{_thresholds['slow_request_ms']} ms.",
                "since": None,
                "link": "/app/platform/diagnostics/performance",
            }
        )
    errors = last["status"].get("5xx", 0)
    if n >= MIN_REQUESTS_FOR_ERRORS and errors / n >= SERVER_ERROR_SHARE:
        out.append(
            {
                "id": "perf:errors",
                "level": "error",
                "area": "performance",
                "title": f"{errors} server errors in the last hour",
                "detail": f"{round(errors * 100 / n)} % of {n} requests "
                "answered with 5xx.",
                "since": None,
                "link": "/app/platform/diagnostics/performance",
            }
        )
    return out
