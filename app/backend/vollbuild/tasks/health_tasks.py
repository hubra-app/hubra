"""Backwards-compatible re-export from vollbuild.core.tasks.health_tasks."""

from vollbuild.core.tasks.health_tasks import (
    annotations,
    HealthCache,
    HealthService,
    celery_app,
    _logger,
    _BEAT_INTERVAL,
    _CACHE_TTL,
    run_health_checks,
)
