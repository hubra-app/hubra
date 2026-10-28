"""Tests for the run_health_checks Celery task."""

from unittest.mock import patch

from hubra.api.health.cache import HealthCache
from hubra.api.health.services import HealthService
from hubra.core.tasks.health_tasks import run_health_checks


def _patch_all(**overrides):
    """Patch all HealthService checks; *overrides* sets specific return values."""
    defaults = {
        "check_db": {"ok": True, "latency_ms": 1},
        "check_redis": {"ok": True, "latency_ms": 1},
        "check_smtp": {"ok": True, "latency_ms": 1},
        "check_imap": {"ok": True, "latency_ms": 1},
    }
    defaults.update(overrides)
    ctxs = []
    for name, retval in defaults.items():
        p = patch.object(HealthService, name, return_value=retval)
        ctxs.append(p)
    return ctxs


def test_run_health_checks_writes_ok_to_cache(app):
    """All services healthy → cache seeded with 'ok'."""
    HealthCache.clear()
    ctxs = _patch_all()
    for c in ctxs:
        c.__enter__()
    try:
        result = run_health_checks.run()
        assert result["status"] == "ok"
        cached = HealthCache.get()
        assert cached is not None
        assert cached["status"] == "ok"
    finally:
        for c in reversed(ctxs):
            c.__exit__(None, None, None)


def test_run_health_checks_writes_degraded_to_cache(app, db):
    """DB+Redis ok, mail enabled but down → 'degraded' in cache."""
    from tests.helpers import set_modules

    set_modules(True, "mail")

    HealthCache.clear()
    ctxs = _patch_all(
        check_smtp={"ok": False, "latency_ms": 0, "error": "not configured"},
        check_imap={"ok": False, "latency_ms": 0, "error": "not configured"},
    )
    for c in ctxs:
        c.__enter__()
    try:
        result = run_health_checks.run()
        assert result["status"] == "degraded"
        cached = HealthCache.get()
        assert cached is not None
        assert cached["status"] == "degraded"
    finally:
        for c in reversed(ctxs):
            c.__exit__(None, None, None)


def test_run_health_checks_writes_error_to_cache(app):
    """DB down → 'error' in cache."""
    HealthCache.clear()
    ctxs = _patch_all(
        check_db={"ok": False, "latency_ms": 1, "error": "connection refused"},
    )
    for c in ctxs:
        c.__enter__()
    try:
        result = run_health_checks.run()
        assert result["status"] == "error"
        cached = HealthCache.get()
        assert cached is not None
        assert cached["status"] == "error"
    finally:
        for c in reversed(ctxs):
            c.__exit__(None, None, None)


def test_run_health_checks_includes_checked_at(app):
    """Task payload includes a checked_at timestamp."""
    HealthCache.clear()
    ctxs = _patch_all()
    for c in ctxs:
        c.__enter__()
    try:
        result = run_health_checks.run()
        assert "checked_at" in result
        assert isinstance(result["checked_at"], float)
    finally:
        for c in reversed(ctxs):
            c.__exit__(None, None, None)


# ── Beat schedule registration ────────────────────────────────────────────────


def test_beat_schedule_contains_health_check():
    """celery_app beat_schedule includes health-check-20s."""
    from hubra.core.tasks import celery_app

    assert "health-check-20s" in celery_app.conf.beat_schedule
    entry = celery_app.conf.beat_schedule["health-check-20s"]
    assert entry["task"] == "hubra.core.tasks.health_tasks.run_health_checks"
    assert entry["schedule"] == 20.0
