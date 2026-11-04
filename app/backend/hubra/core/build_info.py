"""Which commit this process was built from, and what the other processes report.

The image build passes the git commit as ``GIT_SHA``; the backend Dockerfile
turns it into ``HUBRA_GIT_SHA``.  Local runs and images built without it have
none, and manage shows "dev" for them.

Every process of the backend image (the API's gunicorn workers, Celery worker
and beat, the Discord gateway) keeps a short-lived Redis key per process kind
and host (pod) with its commit and version fresh.  Manage shows what each one
runs and spots one left behind after a deploy, and ``services/upgrades.py``
tells when a deploy started and finished.  A process that stopped drops out
after ``_TTL`` seconds.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time

_log = logging.getLogger(__name__)

_KEY_PREFIX = "hubra:build:"
_TTL = 90  # seconds
_INTERVAL = 30  # seconds between refreshes

_started: set[str] = set()


def commit() -> str | None:
    """The full commit hash this process was built from, or None (dev build)."""
    sha = os.environ.get("HUBRA_GIT_SHA", "").strip()
    return sha or None


def version() -> str | None:
    """The app version (pyproject.toml), or None when it can't be read."""
    try:
        from hubra.core.services.version import VersionService

        return VersionService.get_version()
    except Exception:
        return None


def _write(component: str) -> None:
    from hubra.core.redis_client import get_redis_client, mark_redis_down

    client = get_redis_client()
    if client is None:
        return
    host = os.environ.get("HOSTNAME") or "local"
    value = json.dumps(
        {
            "component": component,
            "commit": commit(),
            "version": version(),
            "host": host,
            "seen": int(time.time()),
        }
    )
    try:
        client.set(f"{_KEY_PREFIX}{component}:{host}", value, ex=_TTL)
    except Exception:
        _log.debug("Could not report the build of %s", component, exc_info=True)
        mark_redis_down()


def start_heartbeat(component: str, app=None) -> None:
    """Report *component*'s build now and every half minute, from a daemon thread.

    Needs the Flask app (passed in, or the current one) for ``REDIS_URL``.
    Calling it twice for the same component in one process does nothing.
    """
    if component in _started:
        return
    if app is None:
        from flask import current_app

        app = current_app._get_current_object()
    _started.add(component)

    def loop() -> None:
        while True:
            try:
                with app.app_context():
                    _write(component)
            except Exception:
                _log.debug("Build heartbeat failed for %s", component, exc_info=True)
            time.sleep(_INTERVAL)

    threading.Thread(target=loop, name=f"build-heartbeat-{component}", daemon=True).start()


def reported() -> list[dict]:
    """What the processes reported in the last few minutes: one entry per
    process kind and host, ``{component, host, commit, version, seen}``."""
    from hubra.core.redis_client import get_redis_client, mark_redis_down

    client = get_redis_client()
    if client is None:
        return []
    out: list[dict] = []
    try:
        for key in client.scan_iter(match=f"{_KEY_PREFIX}*", count=100):
            raw = client.get(key)
            if not raw:
                continue
            try:
                entry = json.loads(raw)
            except ValueError:
                continue
            if isinstance(entry, dict) and entry.get("component"):
                out.append(entry)
    except Exception:
        _log.debug("Could not read build reports", exc_info=True)
        mark_redis_down()
        return []
    out.sort(key=lambda e: (str(e.get("component")), str(e.get("host"))))
    return out
