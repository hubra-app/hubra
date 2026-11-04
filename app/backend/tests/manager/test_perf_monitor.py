"""Server performance monitoring: request timing per route, slow queries,
the thresholds as platform settings and manage › Platform › Alerts."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import text

from hubra.core.services import perf_monitor, platform_monitor, platform_settings

BASE = "/api/v1/manager/platform"


@pytest.fixture(autouse=True)
def _defaults():
    perf_monitor.reset_local()
    saved = perf_monitor.thresholds()
    yield
    perf_monitor._thresholds.update(saved)


def _fresh_health():
    import time

    return {"checked_at": time.time(), "services": {}, "watch": {}}


# ── Percentiles ───────────────────────────────────────────────────────────────


def test_percentile_from_buckets():
    b = [0] * (len(perf_monitor.BUCKETS) + 1)
    assert perf_monitor.percentile(b, 0.5) is None
    # 100 requests in (50, 75] ms.
    b[perf_monitor._bucket(60)] = 100
    assert 50 <= perf_monitor.percentile(b, 0.5) <= 75
    assert 50 <= perf_monitor.percentile(b, 0.95) <= 75
    # Five very slow ones move p95 but not p50.
    b[perf_monitor._bucket(4000)] = 6
    assert perf_monitor.percentile(b, 0.5) <= 75
    assert perf_monitor.percentile(b, 0.95) > 3000
    # Beyond the last bucket the estimate stops at its bound.
    b2 = [0] * (len(perf_monitor.BUCKETS) + 1)
    b2[-1] = 3
    assert perf_monitor.percentile(b2, 0.95) == perf_monitor.BUCKETS[-1]


# ── Requests ──────────────────────────────────────────────────────────────────


def test_requests_are_counted_by_route_not_path(client, staff_headers, db):
    for member_id in (1, 2, 99999):
        client.get(f"/api/v1/members/{member_id}?secret=abc")
    data = client.get(f"{BASE}/alerts/performance?hours=1").get_json()
    routes = {(r["method"], r["route"]): r for r in data["routes"]}
    member = next(
        r
        for (m, rule), r in routes.items()
        if m == "GET" and "<" in rule and "members" in rule
    )
    assert member["requests"] == 3
    assert member["p50"] is not None and member["p95"] is not None
    assert sum(member["status"].values()) == 3
    # No path, id or query string anywhere in what is stored.
    blob = repr(perf_monitor._local)
    assert "99999" not in blob and "secret" not in blob and "abc" not in blob
    assert data["total"]["requests"] >= 3
    assert data["lastHour"]["requests"] >= 3
    assert data["source"] == "memory"


def test_status_classes_and_slow_requests(caplog):
    perf_monitor._thresholds["slow_request_ms"] = 500
    perf_monitor.record_request("GET /api/v1/x", 200, 20)
    perf_monitor.record_request("GET /api/v1/x", 404, 30)
    perf_monitor.record_request("GET /api/v1/x", 500, 900, db_ms=700, queries=4)
    (row,) = perf_monitor.summary(1)["routes"]
    assert row["status"] == {"2xx": 1, "4xx": 1, "5xx": 1}
    assert row["slow"] == 1
    assert row["requests"] == 3
    assert row["dbMean"] == 233
    assert row["queriesMean"] == pytest.approx(1.3)


def test_slow_request_is_logged_without_the_path(client, staff_headers, caplog):
    perf_monitor._thresholds["slow_request_ms"] = 1
    perf_monitor._thresholds_at = float("inf")  # keep the test's value
    with patch.object(perf_monitor.time, "monotonic", side_effect=_clock()):
        with caplog.at_level(logging.WARNING, logger=perf_monitor.__name__):
            client.get("/api/v1/members/4242?token=s3cret")
    records = [r for r in caplog.records if r.getMessage() == "slow request"]
    assert records
    assert "<" in records[0].route and "4242" not in records[0].route
    assert "s3cret" not in repr(records[0].__dict__)


def _clock():
    """monotonic() that moves 10 ms per call."""
    t = 1000.0
    while True:
        t += 0.01
        yield t


def test_skips_health_and_options(client):
    client.get("/health")
    client.options("/api/v1/members")
    assert perf_monitor.summary(1)["total"]["requests"] == 0


# ── Queries ───────────────────────────────────────────────────────────────────


def test_normalize_sql_drops_values():
    sql = (
        "SELECT * FROM members WHERE email = 'anna@example.ch' AND id = 42 "
        "AND tier_id IN (%(tier_id_1_1)s, %(tier_id_1_2)s, %(tier_id_1_3)s) "
        "AND name = %(name_1)s AND x = 1.5 AND col_2 = ?"
    )
    out = perf_monitor.normalize_sql(sql)
    assert "anna" not in out and "42" not in out and "1.5" not in out
    assert "tier_id_1" not in out and "name_1" not in out
    assert "col_2" in out  # identifiers stay
    assert out.count("?") >= 5
    assert len(perf_monitor.normalize_sql("SELECT " + "a, " * 500)) <= 401


def test_slow_query_is_counted_and_logged(app, db, caplog):
    perf_monitor._thresholds["slow_query_ms"] = 1
    with patch.object(perf_monitor.time, "monotonic", side_effect=_clock()):
        with caplog.at_level(logging.WARNING, logger=perf_monitor.__name__):
            db.session.execute(
                text("SELECT :v AS secret_value WHERE 'mail@x.ch' = 'mail@x.ch'"),
                {"v": "member-data"},
            )
    records = [r for r in caplog.records if r.getMessage() == "slow query"]
    assert records
    assert "member-data" not in repr(records[-1].__dict__)
    assert "mail@x.ch" not in records[-1].sql
    queries = perf_monitor.summary(1)["queries"]
    q = next(q for q in queries if "secret_value" in q["sql"])
    assert q["count"] >= 1 and q["maxMs"] >= 1
    assert "member-data" not in repr(queries)


def test_fast_queries_are_not_stored(db):
    perf_monitor._thresholds["slow_query_ms"] = 600000
    db.session.execute(text("SELECT 1"))
    assert perf_monitor.summary(1)["queries"] == []


# ── Settings ──────────────────────────────────────────────────────────────────


def test_thresholds_come_from_platform_settings(db):
    platform_settings.set_many({"perf.slow_query_ms": "75", "perf.p95_warning_ms": "0"})
    db.session.commit()
    perf_monitor.refresh_thresholds(force=True)
    assert perf_monitor.thresholds() == {
        "slow_request_ms": 1000,
        "slow_query_ms": 75,
        "p95_warning_ms": 0,
    }
    with pytest.raises(platform_settings.PlatformSettingError):
        platform_settings.set_many({"perf.slow_query_ms": "fast"})


# ── Alerts overview ───────────────────────────────────────────────────────────


def test_slow_api_and_server_errors_are_open_problems(db):
    perf_monitor._thresholds["p95_warning_ms"] = 500
    perf_monitor._thresholds_at = float("inf")
    for i in range(60):
        perf_monitor.record_request("GET /api/v1/x", 500 if i < 6 else 200, 2000)
    with patch("hubra.core.services.health_cache.HealthCache.get", return_value=_fresh_health()):
        ids = {p["id"] for p in platform_monitor.open_problems()}
    assert {"perf:slow", "perf:errors"} <= ids


def test_old_hours_do_not_count_in_the_last_hour(db):
    perf_monitor._thresholds["p95_warning_ms"] = 500
    perf_monitor._thresholds_at = float("inf")
    old = datetime(2020, 1, 1, tzinfo=timezone.utc)
    for _ in range(60):
        perf_monitor.record_request("GET /api/v1/x", 500, 2000, at=old)
    assert perf_monitor.problems() == []


def test_performance_endpoint_is_staff_only(client, auth_headers):
    assert client.get(f"{BASE}/alerts/performance").status_code == 403


def test_performance_endpoint_rejects_bad_hours(client, staff_headers):
    assert client.get(f"{BASE}/alerts/performance?hours=x").status_code == 400
    assert client.get(f"{BASE}/alerts/performance?hours=999").get_json()["hours"] == 24


# ── Held back by the container ───────────────────────────────────────────────


def test_slow_query_says_when_the_pod_was_throttled(app, db):
    """A trivial statement that is slow while the pod was throttled waited
    for the CPU, not for the database; the count says so."""
    from flask import g

    from hubra.core import cgroup

    perf_monitor._thresholds["slow_query_ms"] = 1
    now = {"p": cgroup.Pressure(1000, 0)}
    with patch.object(cgroup, "pressure", side_effect=lambda: now["p"]):
        perf_monitor.mark_start()
        now["p"] = cgroup.Pressure(51000, 0)  # 50 ms throttled
        with patch.object(perf_monitor.time, "monotonic", side_effect=_clock()):
            db.session.execute(text("SELECT 41 AS throttled_probe"))
        perf_monitor.mark_start()  # a new task
        now["p"] = cgroup.Pressure(51000, 1)  # memory reached its limit
        with patch.object(perf_monitor.time, "monotonic", side_effect=_clock()):
            db.session.execute(text("SELECT 42 AS throttled_probe"))
    g.pop("_perf_pressure", None)
    q = next(
        q for q in perf_monitor.summary(1)["queries"] if "throttled_probe" in q["sql"]
    )
    assert q["count"] == 2
    assert q["cpuThrottled"] == 1
    assert q["memoryLimit"] == 1


def test_no_cgroup_means_no_tags(app, db):
    perf_monitor._thresholds["slow_query_ms"] = 1
    perf_monitor.mark_start()
    with patch.object(perf_monitor.time, "monotonic", side_effect=_clock()):
        db.session.execute(text("SELECT 43 AS untagged_probe"))
    q = next(
        q for q in perf_monitor.summary(1)["queries"] if "untagged_probe" in q["sql"]
    )
    assert (q["cpuThrottled"], q["memoryLimit"]) == (0, 0)


# ── Requests without a route ─────────────────────────────────────────────────


def test_path_shape_keeps_no_ids_or_tokens():
    shape = perf_monitor.path_shape
    assert shape("/wp-admin/setup-config.php") == "/wp-admin/setup-config.php"
    assert shape("/.env") == "/*"  # starts with a dot: not word-like
    assert shape("/invite/3f9a2b77c0") == "/invite/*"
    assert shape("/api/v1/members/42/notes") == "/api/v1/members/*/…"
    assert shape("/a/b/c/d/e/f") == "/a/b/c/d/…"
    assert shape("/") == "/"


def test_unmatched_paths_are_counted_by_shape(client, staff_headers):
    client.get("/wp-login.php")
    client.get("/old/path/123")
    client.get("/old/path/456")
    data = client.get(f"{BASE}/alerts/performance?hours=1").get_json()
    got = {(u["method"], u["path"]): u["count"] for u in data["unmatched"]}
    assert got[("GET", "/wp-login.php")] == 1
    assert got[("GET", "/old/path/*")] == 2
    assert not any("123" in p for _, p in got)


def test_unmatched_shapes_are_capped(monkeypatch):
    monkeypatch.setattr(perf_monitor, "_UNMATCHED_MAX", 3)
    for word in ("alpha", "beta", "gamma", "delta", "epsilon"):
        perf_monitor.record_unmatched("GET", f"/{word}")
    perf_monitor.record_unmatched("GET", "/alpha")
    got = {u["path"]: u["count"] for u in perf_monitor.summary(1)["unmatched"]}
    assert got["/alpha"] == 2
    assert got["(other)"] == 2
    assert len(got) == 4
