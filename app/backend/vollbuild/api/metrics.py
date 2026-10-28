"""Per-tenant API call counting and error rate tracking middleware.

Registers Flask before/after request hooks that increment Redis counters
for every counted request, scoped to the current tenant and calendar month.
Counters auto-expire after 45 days (covers the 30-day window + buffer).

Follows the logging_config.py middleware pattern and the permissions.py
Redis pattern with negative-cache fallback.
"""

from __future__ import annotations

import time
import logging
from datetime import datetime, timezone

from flask import Flask, g, request, current_app

_log = logging.getLogger(__name__)

# Paths that should never be counted
_SKIP_PREFIXES = ("/health", "/api/v1/health")
_SKIP_METHODS = {"OPTIONS", "HEAD"}

# Redis key prefix and TTL (45 days)
_KEY_PREFIX = "api:calls:"
_ERROR_KEY_PREFIX = "api:errors:"
_KEY_TTL_SECONDS = 45 * 24 * 60 * 60

# Redis negative-cache — avoid hammering Redis when it's down
_REDIS_DOWN_WINDOW = 5.0
_redis_down_until: float = 0.0


def _get_redis_client():
    """Return a Redis client or None if Redis is unavailable."""
    global _redis_down_until
    if time.monotonic() < _redis_down_until:
        return None
    try:
        url = current_app.config.get("REDIS_URL", "")
        if not url or url == "memory://":
            return None
        import redis as redis_lib

        return redis_lib.from_url(url, socket_connect_timeout=0.3, socket_timeout=0.3)
    except Exception:
        _mark_redis_down()
        return None


def _mark_redis_down() -> None:
    global _redis_down_until
    _redis_down_until = time.monotonic() + _REDIS_DOWN_WINDOW


def _redis_key(tenant_id: int, dt: datetime) -> str:
    """Build Redis key for a tenant+month: api:calls:{tenant_id}:{YYYY-MM}."""
    return f"{_KEY_PREFIX}{tenant_id}:{dt.strftime('%Y-%m')}"


def _error_redis_key(dt: datetime) -> str:
    """Build Redis key for global error tracking: api:errors:{count|total}:{YYYY-MM}."""
    return f"{_ERROR_KEY_PREFIX}count:{dt.strftime('%Y-%m')}"


def _total_redis_key(dt: datetime) -> str:
    """Build Redis key for global total tracking: api:errors:total:{YYYY-MM}."""
    return f"{_ERROR_KEY_PREFIX}total:{dt.strftime('%Y-%m')}"


def configure_api_counting(app: Flask) -> None:
    """Attach per-tenant API call counting to *app*."""

    @app.before_request
    def _counting_before() -> None:
        # Skip counting for excluded methods and paths
        if request.method in _SKIP_METHODS:
            return
        if any(request.path.startswith(p) for p in _SKIP_PREFIXES):
            return
        # Record start time for potential future use (e.g., latency tracking)
        g._api_count_start = time.monotonic()

    @app.after_request
    def _counting_after(response):
        # Skip if the before hook was skipped
        if not hasattr(g, "_api_count_start"):
            return response

        # Skip if no tenant resolved
        tenant = getattr(g, "tenant", None)

        # Track global error/total rates for all requests (not just tenant ones)
        try:
            client = _get_redis_client()
            if client is not None:
                now = datetime.now(timezone.utc)
                pipe = client.pipeline()
                # Always increment total requests
                pipe.incr(_total_redis_key(now))
                pipe.expire(_total_redis_key(now), _KEY_TTL_SECONDS)
                # Increment error count for 4xx/5xx
                if response.status_code >= 400:
                    pipe.incr(_error_redis_key(now))
                    pipe.expire(_error_redis_key(now), _KEY_TTL_SECONDS)
                pipe.execute()
                client.close()
        except Exception:
            _mark_redis_down()
            _log.debug("API error rate counter failed", exc_info=True)

        # Skip tenant call counting for errors and unauthenticated requests
        if response.status_code >= 400 or tenant is None:
            return response

        # Increment tenant-specific counter in Redis (fire-and-forget)
        try:
            client = _get_redis_client()
            if client is not None:
                key = _redis_key(tenant.id, datetime.now(timezone.utc))
                pipe = client.pipeline()
                pipe.incr(key)
                pipe.expire(key, _KEY_TTL_SECONDS)
                pipe.execute()
                client.close()
        except Exception:
            _mark_redis_down()
            _log.debug("API call count increment failed", exc_info=True)

        return response


def get_api_calls_30d(tenant_id: int) -> int:
    """Return the total API calls for the given tenant in the last 30 days.

    Sums across the current month and the two previous months to cover
    the full 30-day rolling window.
    """
    try:
        client = _get_redis_client()
        if client is None:
            return 0

        now = datetime.now(timezone.utc)
        total = 0

        # Check current month and two previous months
        for months_ago in range(3):
            # Calculate month offset manually (avoid dateutil dependency)
            year = now.year
            month = now.month - months_ago
            while month <= 0:
                month += 12
                year -= 1
            dt = datetime(year, month, 1, tzinfo=timezone.utc)

            key = _redis_key(tenant_id, dt)
            val = client.get(key)
            if val is not None:
                total += int(val)

        client.close()
        return total
    except Exception:
        _log.debug("Failed to read API call counts", exc_info=True)
        return 0


def get_metrics_summary() -> dict:
    """Aggregate platform metrics from Redis counters.

    Returns a dict with total calls, error count, error rate, and
    per-tenant breakdown for the current month.
    """
    from vollbuild.extensions import db
    from vollbuild.core.models.tenant import Tenant
    from sqlalchemy import select as _select

    try:
        client = _get_redis_client()
        if client is None:
            return {
                "total_calls": 0,
                "total_errors": 0,
                "error_rate": 0.0,
                "tenants": [],
            }

        now = datetime.now(timezone.utc)
        dt = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

        # Global error/total counts
        error_count = client.get(_error_redis_key(dt))
        total_count = client.get(_total_redis_key(dt))
        total_errors = int(error_count) if error_count else 0
        total_all = int(total_count) if total_count else 0

        # Per-tenant call counts
        tenants = list(
            db.session.scalars(_select(Tenant).where(Tenant.status == "active")).all()
        )

        tenant_summaries = []
        total_calls = 0

        for tenant in tenants:
            calls_key = _redis_key(tenant.id, dt)
            calls_val = client.get(calls_key)
            calls = int(calls_val) if calls_val else 0
            total_calls += calls

            tenant_summaries.append(
                {
                    "tenant_id": tenant.id,
                    "slug": tenant.slug,
                    "name": tenant.name,
                    "calls": calls,
                }
            )

        client.close()

        return {
            "total_calls": total_calls,
            "total_errors": total_errors,
            "error_rate": round(total_errors / total_all * 100, 2)
            if total_all > 0
            else 0.0,
            "tenants": tenant_summaries,
        }
    except Exception:
        _log.debug("Failed to aggregate platform metrics", exc_info=True)
        return {"total_calls": 0, "total_errors": 0, "error_rate": 0.0, "tenants": []}
