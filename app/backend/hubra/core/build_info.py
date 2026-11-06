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

Processes that import plugin code (the club API, Celery) also report how
each installed plugin loaded there, so manage, which runs in a backend that
only reads plugin manifests, can show an import error that only the club
backend hits (:func:`plugin_errors`).
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
_READ_TIMEOUT = 1.0  # seconds, for reading all reports

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
            "plugins": _plugin_report(),
        }
    )
    try:
        client.set(f"{_KEY_PREFIX}{component}:{host}", value, ex=_TTL)
    except Exception:
        _log.debug("Could not report the build of %s", component, exc_info=True)
        mark_redis_down()


def _plugin_report() -> dict | None:
    """How each installed plugin loaded in this process: ``{id: {version,
    loaded, error}}``; None where plugin code isn't imported (manifest-only
    roles), so their reports never hide or raise an error."""
    try:
        from hubra.core.plugins.loader import current, loads_plugin_code

        if not loads_plugin_code():
            return None
        found = current()
        out = {}
        for pid in sorted(found.wanted):
            spec = found.get(pid)
            if spec is None:
                continue
            out[pid] = {
                "version": spec.version,
                "loaded": bool(spec.loaded),
                "error": (spec.error or "")[:500],
            }
        return out
    except Exception:
        _log.debug("Could not report the plugins of this process", exc_info=True)
        return None


def plugin_errors(reports: list[dict] | None = None) -> dict[str, list[dict]]:
    """Plugins that failed to load in another process, by plugin id:
    ``[{component, host, version, error}]``, from the build reports."""
    out: dict[str, list[dict]] = {}
    for entry in reported() if reports is None else reports:
        plugins = entry.get("plugins")
        if not isinstance(plugins, dict):
            continue
        for pid, info in plugins.items():
            if (
                not isinstance(info, dict)
                or info.get("loaded")
                or not info.get("error")
            ):
                continue
            out.setdefault(str(pid), []).append(
                {
                    "component": str(entry.get("component") or ""),
                    "host": str(entry.get("host") or ""),
                    "version": str(info.get("version") or ""),
                    "error": str(info["error"]),
                }
            )
    return out


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
    process kind and host, ``{component, host, commit, version, seen}``.
    Empty when Redis is off or could not be read (see :func:`read_reports`)."""
    return read_reports() or []


def read_reports() -> list[dict] | None:
    """:func:`reported`, or None when Redis is configured but did not answer.

    The scan takes a few round trips, so it gets a longer timeout than the
    per-request caches, and a slow answer does not trip the shared circuit
    breaker (``mark_redis_down``): that would also blank every other Redis
    read of this process for a few seconds, such as the health cache.
    """
    import redis as redis_lib

    from hubra.core.redis_client import get_redis_client, mark_redis_down

    client = get_redis_client(timeout=_READ_TIMEOUT)
    if client is None:
        return [] if not _redis_configured() else None
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
    except redis_lib.TimeoutError:
        _log.warning("Build reports: Redis did not answer in %ss", _READ_TIMEOUT)
        return None
    except Exception:
        _log.debug("Could not read build reports", exc_info=True)
        mark_redis_down()
        return None
    out.sort(key=lambda e: (str(e.get("component")), str(e.get("host"))))
    return out


def _redis_configured() -> bool:
    from flask import current_app

    url = current_app.config.get("REDIS_URL", "")
    return bool(url) and url != "memory://"
