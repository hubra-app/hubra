"""Celery task that repopulates the health-status cache periodically.

Registered in the beat schedule (every 20s) so the public ``/health`` endpoint
can read an instantly-available cached status instead of running live
dependency checks on every request.
"""

from __future__ import annotations

import logging
import time

from hubra.api.health.cache import HealthCache
from hubra.api.health.services import HealthService
from hubra.core.tasks import celery_app

_logger = logging.getLogger(__name__)

_BEAT_INTERVAL = 20  # seconds — matches beat_schedule entry
_CACHE_TTL = 90  # seconds — 4.5× the beat interval


@celery_app.task(name="hubra.core.tasks.health_tasks.run_health_checks")
def run_health_checks() -> dict:
    """Run all health checks concurrently and write the result to the cache.

    Returns the payload so the task result is inspectable.
    """
    from hubra.core.services import platform_monitor

    checked_at = time.time()
    previous = HealthCache.get()
    payload = HealthService.run_all_checks()
    payload["checked_at"] = checked_at
    try:
        platform_monitor.watch_services(previous, payload)
    except Exception:
        _logger.warning("health-check: watching services failed", exc_info=True)
    HealthCache.set(payload, ttl=_CACHE_TTL)
    _logger.info("health-check: status=%s", payload["status"])
    return payload
