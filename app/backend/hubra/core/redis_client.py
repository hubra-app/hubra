"""Shared Redis client for caches, with a short circuit breaker.

Callers treat Redis as optional: ``get_redis_client()`` returns None when
``REDIS_URL`` is unset (or ``memory://``), or for a few seconds after any
caller reported a failure via ``mark_redis_down()``. That keeps an outage
from adding a socket timeout to every request.
"""

from __future__ import annotations

import logging
import time

from flask import current_app

_log = logging.getLogger(__name__)

_DOWN_WINDOW = 5.0  # seconds
_down_until: float = 0.0  # monotonic timestamp; 0 = not down
_clients: dict[tuple[str, float], object] = {}


def get_redis_client(timeout: float = 0.3):
    """Return a cached Redis client for ``REDIS_URL``, or None if unavailable."""
    if time.monotonic() < _down_until:
        return None
    try:
        url = current_app.config.get("REDIS_URL", "")
        if not url or url == "memory://":
            return None
        key = (url, timeout)
        client = _clients.get(key)
        if client is None:
            import redis as redis_lib

            client = redis_lib.from_url(
                url, socket_connect_timeout=timeout, socket_timeout=timeout
            )
            _clients[key] = client
        return client
    except Exception:
        _log.debug("Redis client creation failed", exc_info=True)
        return None


def mark_redis_down() -> None:
    """Record that Redis is unreachable, suppressing further attempts briefly."""
    global _down_until
    _down_until = time.monotonic() + _DOWN_WINDOW


def reset_redis_down() -> None:
    """Clear the circuit breaker (tests)."""
    global _down_until
    _down_until = 0.0
