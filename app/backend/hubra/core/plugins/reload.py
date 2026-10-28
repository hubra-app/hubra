"""Reloading every process after a plugin was installed, updated or removed.

Flask cannot add or drop blueprints in a running app, so plugins change
by restarting processes.  The installer bumps ``plugin_state.generation``;
every long-running process checks it every ``PLUGINS_RELOAD_POLL``
seconds and, when it changed:

- gunicorn (``gunicorn.conf.py``): the arbiter gets SIGHUP and replaces
  its workers gracefully; the new workers load the new plugin set.
- Celery worker and beat: the process stops gracefully (SIGTERM) and
  Docker or Kubernetes starts it again.

The check uses its own short-lived database connection, so it works in
the gunicorn arbiter, which has no Flask app.
"""

from __future__ import annotations

import logging
import os
import signal
import threading
import time

_log = logging.getLogger(__name__)


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    return url


def read_generation(engine) -> int | None:
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            value = conn.execute(
                text("SELECT value FROM plugin_state WHERE key = 'generation'")
            ).scalar()
    except Exception:
        return None  # no table yet, or the database is away for a moment
    try:
        return int(value) if value is not None else 0
    except ValueError:
        return 0


def watch(
    on_change, interval: float, url: str | None = None
) -> threading.Thread | None:
    """Call *on_change(old, new)* once when the generation changes."""
    url = url or _database_url()
    if interval <= 0 or not url or url.startswith("sqlite"):
        return None
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    engine = create_engine(url, poolclass=NullPool)

    def loop():
        start = read_generation(engine)
        while True:
            time.sleep(interval)
            now = read_generation(engine)
            if now is None:
                continue
            if start is None:
                start = now
                continue
            if now != start:
                _log.warning(
                    "Plugins changed (generation %s -> %s): reloading", start, now
                )
                try:
                    on_change(start, now)
                finally:
                    start = now

    t = threading.Thread(target=loop, name="hubra-plugin-watch", daemon=True)
    t.start()
    return t


def interval() -> float:
    try:
        return float(os.environ.get("HUBRA_PLUGINS_RELOAD_POLL", 15))
    except ValueError:
        return 15.0


def watch_gunicorn(arbiter) -> None:
    """From gunicorn's ``when_ready``: SIGHUP the arbiter on a change."""
    watch(lambda _old, _new: os.kill(arbiter.pid, signal.SIGHUP), interval())


def watch_celery() -> None:
    """From Celery's ``worker_ready`` / ``beat_init``: stop gracefully on a change."""
    watch(lambda _old, _new: os.kill(os.getpid(), signal.SIGTERM), interval())
