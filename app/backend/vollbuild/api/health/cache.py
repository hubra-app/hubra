"""Health status cache — shared across workers via Redis with an in-memory fallback.

The public ``/health`` endpoint reads from this cache (instant) instead of
running live dependency checks on every request.  A Celery beat task
(:mod:`vollbuild.core.tasks.health_tasks`) repopulates the cache periodically.

When ``REDIS_URL`` is unset or ``memory://`` (testing / dev without Redis),
a process-local dict is used instead.
"""

from __future__ import annotations

import logging
import time
from typing import Any

_logger = logging.getLogger(__name__)

_CACHE_KEY = "health:status"
_DEFAULT_TTL = 90  # seconds — 4.5× the 20s beat interval, tolerant of brief delays

# ── In-memory fallback (used when Redis is not configured) ───────────────────
# {key: (payload, expires_at_monotonic)}
_mem_store: dict[str, tuple[dict, float]] = {}


def _get_redis_client():
    """Return a Redis client if available, else None."""
    try:
        from flask import current_app

        url = current_app.config.get("REDIS_URL", "")
        if not url or url == "memory://":
            return None
        import redis as redis_lib

        return redis_lib.from_url(url, socket_connect_timeout=1, socket_timeout=1)
    except Exception:
        return None


class HealthCache:
    """Cached health status, backed by Redis or an in-memory dict."""

    @staticmethod
    def get() -> dict | None:
        """Return the cached health payload, or None if missing/expired."""
        client = _get_redis_client()
        if client is not None:
            try:
                raw = client.get(_CACHE_KEY)
                if raw is None:
                    return None
                import json

                return json.loads(raw)
            except Exception:
                _logger.debug("Health cache read failed")
                return None

        entry = _mem_store.get(_CACHE_KEY)
        if entry is None:
            return None
        payload, expires_at = entry
        if time.monotonic() >= expires_at:
            _mem_store.pop(_CACHE_KEY, None)
            return None
        return payload

    @staticmethod
    def set(payload: dict[str, Any], ttl: int = _DEFAULT_TTL) -> None:
        """Store *payload* with the given TTL (seconds)."""
        client = _get_redis_client()
        if client is not None:
            try:
                import json

                client.setex(_CACHE_KEY, ttl, json.dumps(payload))
                return
            except Exception:
                _logger.debug("Health cache write failed")

        _mem_store[_CACHE_KEY] = (payload, time.monotonic() + ttl)

    @staticmethod
    def clear() -> None:
        """Remove the cached entry (used by tests and on-demand refresh)."""
        client = _get_redis_client()
        if client is not None:
            try:
                client.delete(_CACHE_KEY)
            except Exception:
                _logger.debug("Health cache clear failed")
        _mem_store.pop(_CACHE_KEY, None)
