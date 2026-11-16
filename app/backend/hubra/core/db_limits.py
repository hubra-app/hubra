"""Postgres time limits per process: API, worker, or none (CLI, migrations).

A query that never ends or a transaction left open holds a gunicorn worker
or a Celery child, its connection and its locks. Each new connection of an
API or worker process gets

- ``statement_timeout``: the longest one statement may run,
- ``idle_in_transaction_session_timeout``: how long a transaction may sit
  open with nothing running (a forgotten commit, a network call made in the
  middle of one),

and every connection gets TCP keepalives (``ProductionConfig``), so a
connection whose peer vanished fails within about a minute instead of
waiting forever.

API and worker connections also name their process in ``application_name``
(``hubra-api``, ``hubra-platform-worker``, ...; the rest show ``hubra``), so
``pg_stat_activity`` says which process holds them. :func:`pool_options`
sizes each process's pool.

The CLI (``flask db upgrade``, seeds, ``flask backups``) has no limits: it is
the process kind until gunicorn's ``post_worker_init`` or Celery's
``worker_process_init`` calls :func:`use`. Values are milliseconds; 0 turns a
limit off.

==========  ======================  ==================================
process     statement_timeout       idle_in_transaction_session_timeout
==========  ======================  ==================================
api         60 s                    120 s (gunicorn's --timeout)
worker      5 min                   off (backups wait on pg_dump)
==========  ======================  ==================================
"""

from __future__ import annotations

import logging
import os

from sqlalchemy import event
from sqlalchemy.engine import Engine

_log = logging.getLogger(__name__)

DEFAULTS = {
    "api": {"statement": 60_000, "idle_in_tx": 120_000},
    # No idle limit in the worker: a backup keeps its transaction open while
    # pg_dump (its own connection) runs for as long as it takes.
    "worker": {"statement": 5 * 60_000, "idle_in_tx": 0},
}

_kind: str | None = None
_installed = False


def limits(kind: str | None) -> dict[str, int]:
    """The limits for *kind*, with ``DB_STATEMENT_TIMEOUT_MS_<KIND>`` and
    ``DB_IDLE_IN_TX_TIMEOUT_MS_<KIND>`` overriding the defaults."""
    if kind not in DEFAULTS:
        return {}
    out = {}
    for key, env in (
        ("statement", "DB_STATEMENT_TIMEOUT_MS"),
        ("idle_in_tx", "DB_IDLE_IN_TX_TIMEOUT_MS"),
    ):
        raw = os.environ.get(f"{env}_{kind.upper()}")
        try:
            out[key] = int(raw) if raw not in (None, "") else DEFAULTS[kind][key]
        except ValueError:
            out[key] = DEFAULTS[kind][key]
    return out


def use(kind: str, engine: Engine | None = None) -> None:
    """Make this process an ``api`` or ``worker`` process. Connections opened
    from now on get its limits; with *engine*, the pool is emptied so none
    of the connections opened before (at app start) is reused."""
    global _kind
    _kind = kind
    install()
    if engine is not None:
        engine.dispose(close=False)


def current() -> str | None:
    return _kind


def install() -> None:
    global _installed
    if not _installed:
        event.listen(Engine, "connect", _on_connect)
        _installed = True


def _on_connect(dbapi_conn, _record) -> None:
    lim = limits(_kind)
    if not lim:
        return
    module = type(dbapi_conn).__module__ or ""
    if not module.startswith("psycopg"):
        return  # SQLite in tests and development
    try:
        cur = dbapi_conn.cursor()
        # Names are letters, digits and dashes only (roles.build_component).
        cur.execute(f"SET application_name = '{application_name(_kind)}'")
        cur.execute(f"SET statement_timeout = {int(lim['statement'])}")
        cur.execute(
            f"SET idle_in_transaction_session_timeout = {int(lim['idle_in_tx'])}"
        )
        cur.close()
        # psycopg2 opened a transaction for the SETs; end it so the
        # connection reaches the pool idle (SET survives the commit).
        dbapi_conn.commit()
    except Exception:  # a limit is a guard rail, never a reason not to connect
        _log.warning("could not set the %s database limits", _kind, exc_info=True)


# Connections each process keeps open while idle, and how many more it may
# open for a moment. Every gunicorn worker, Celery child, beat and Celery
# parent has its own pool, and SQLAlchemy keeps up to pool_size connections
# open for good once a burst has used them (pool_recycle only replaces them
# on the next checkout, it never closes an idle one). The overflow ones are
# closed when they come back, so a small pool_size caps what sits idle
# without capping how many a busy worker can use. Celery children need two
# at most (the task, plus the lock of a scheduled job), so 2 fits them.
POOL_DEFAULTS = {"pool_size": 2, "max_overflow": 8}


def pool_options() -> dict[str, int]:
    """``pool_size`` and ``max_overflow``, with ``DB_POOL_SIZE`` and
    ``DB_MAX_OVERFLOW`` overriding the defaults."""
    out = {}
    for key, env in (
        ("pool_size", "DB_POOL_SIZE"),
        ("max_overflow", "DB_MAX_OVERFLOW"),
    ):
        raw = os.environ.get(env, "").strip()
        try:
            out[key] = max(0, int(raw)) if raw else POOL_DEFAULTS[key]
        except ValueError:
            out[key] = POOL_DEFAULTS[key]
    if out["pool_size"] == 0:
        out["pool_size"] = 1  # SQLAlchemy reads 0 as "no limit"
    return out


def application_name(kind: str | None) -> str:
    """What pg_stat_activity shows for this process's connections, e.g.
    ``hubra-api``, ``hubra-platform-worker``, so idle connections can be
    told apart by process."""
    if not kind:
        return "hubra"
    try:
        from hubra.core.roles import build_component

        return f"hubra-{build_component(kind)}"[:63]
    except Exception:
        return f"hubra-{kind}"


# Keepalives for psycopg2 connections: probe after 30 s idle, every 10 s,
# give up after 3 misses.
KEEPALIVES = {
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 3,
}
