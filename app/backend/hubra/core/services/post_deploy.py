"""Post-deploy steps: the worker runs migrations, seeds and the permission
sync itself once a new build is rolled out.

Compose runs these steps in its ``flask-init`` container on every start.  A
cluster whose manifests start the backend with plain gunicorn (the image's
``CMD``) never runs them, so each release used to say "run ``flask db
upgrade``, ``flask seed``, ``flask sync-permissions``" by hand.

When ``upgrades.check`` sees every process on a new build (``upgrade.done``),
or on a fresh install's first check, it queues :func:`run` on the default
queue (a club worker, which loads the club routes and plugins the permission
sync reads).  The run:

1. takes the init lock (``hubra.core.startup_lock``) without waiting: an
   init step that holds it does the same work, so this run is skipped;
2. runs the same steps as Compose's init, in order, and stops at the first
   that fails;
3. writes one platform event (category ``system``, kind
   ``upgrade.steps``) with each step's outcome and output, which manage
   shows under Diagnostics › System health.  A failure also alerts the
   platform admins (alert type ``upgrades``).

Every step is safe to run again, so a build that already ran them is only
skipped to keep the log short.  The platform setting
``upgrades.post_deploy_steps`` (on by default) turns it off; manage can
still start a run by hand.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from contextlib import contextmanager

from flask import current_app
from sqlalchemy import select, text

from hubra.core.extensions import db
from hubra.core.models.platform_event import PlatformEvent

logger = logging.getLogger(__name__)

KIND = "upgrade.steps"
SETTING = "upgrades.post_deploy_steps"
# Output kept per step in the event, in characters (the tail).
OUTPUT_LIMIT = 2000

# (key, label, CLI arguments) in the order Compose's init runs them.
STEPS: tuple[tuple[str, str, list[str]], ...] = (
    ("migrate", "flask db upgrade", []),
    ("tenant_schemas", "flask sync-tenant-schemas", ["sync-tenant-schemas"]),
    ("permissions", "flask sync-permissions", ["sync-permissions"]),
    ("seed", "flask seed --skip-migrate", ["seed", "--skip-migrate"]),
    ("plugins", "flask plugins sync", ["plugins", "sync"]),
)


def enabled() -> bool:
    from hubra.core.services import platform_settings

    try:
        return platform_settings.get(SETTING) != "off"
    except Exception:
        logger.debug("post_deploy_setting_unreadable", exc_info=True)
        return True


def last_run() -> dict | None:
    """The newest post-deploy run for manage, or None."""
    try:
        event = db.session.execute(
            select(PlatformEvent)
            .where(PlatformEvent.category == "system")
            .where(PlatformEvent.kind == KIND)
            .order_by(PlatformEvent.id.desc())
            .limit(1)
        ).scalar_one_or_none()
    except Exception:
        logger.debug("post_deploy_last_run_failed", exc_info=True)
        return None
    return event.to_dict() if event else None


def ran_for(build_key: str) -> bool:
    """Whether a run for this build is already in the log."""
    rows = db.session.execute(
        select(PlatformEvent.details)
        .where(PlatformEvent.category == "system")
        .where(PlatformEvent.kind == KIND)
        .order_by(PlatformEvent.id.desc())
        .limit(20)
    ).scalars()
    return any((d or {}).get("build") == build_key for d in rows)


@contextmanager
def _init_lock():
    """The init lock from ``startup_lock``, without waiting.  Yields False
    when another process holds it.  No lock without Postgres (tests, SQLite)."""
    from hubra.core.startup_lock import LOCK_KEY

    engine = db.engine
    if engine.dialect.name != "postgresql":
        yield True
        return
    conn = engine.connect()
    try:
        got = conn.execute(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": LOCK_KEY}
        ).scalar()
        conn.commit()
        try:
            yield bool(got)
        finally:
            if got:
                conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK_KEY})
                conn.commit()
    finally:
        conn.close()


def _migrate() -> str:
    from flask_migrate import upgrade

    upgrade()
    return "Migrations applied."


def _cli(args: list[str]) -> Callable[[], str]:
    def run_cli() -> str:
        result = current_app.test_cli_runner().invoke(args=args, catch_exceptions=True)
        if result.exception is not None and not isinstance(
            result.exception, SystemExit
        ):
            raise result.exception
        if result.exit_code:
            raise RuntimeError(result.output.strip() or f"exit code {result.exit_code}")
        return result.output

    return run_cli


def _steps() -> list[tuple[str, str, Callable[[], str]]]:
    return [
        (key, label, _migrate if not args else _cli(args)) for key, label, args in STEPS
    ]


def run(
    build_key: str | None = None,
    *,
    trigger: str = "deploy",
    actor_id: int | None = None,
) -> dict:
    """Run every step once; returns ``{"state": ..., "steps": [...]}``.

    ``state`` is ``done``, ``failed``, ``locked`` (an init step runs them) or
    ``off`` (the platform setting, only for automatic runs)."""
    from hubra.core.services import platform_monitor, upgrades
    from hubra.core import build_info

    if trigger != "manual" and not enabled():
        return {"state": "off", "steps": []}
    build = {"commit": build_info.commit(), "version": build_info.version()}
    build_key = build_key or upgrades.build_key(build)

    with _init_lock() as got:
        if not got:
            return {"state": "locked", "steps": []}
        results: list[dict] = []
        failed = False
        for key, label, step in _steps():
            if failed:
                results.append({"key": key, "label": label, "state": "skipped"})
                continue
            started = time.monotonic()
            try:
                output = step() or ""
                state = "done"
            except Exception as exc:  # noqa: BLE001 - every failure is reported
                db.session.rollback()
                logger.warning("post_deploy_step_failed step=%s", key, exc_info=True)
                output = f"{type(exc).__name__}: {exc}"
                state = "failed"
                failed = True
            results.append(
                {
                    "key": key,
                    "label": label,
                    "state": state,
                    "seconds": round(time.monotonic() - started, 1),
                    "output": output.strip()[-OUTPUT_LIMIT:],
                }
            )

    overall = "failed" if failed else "done"
    who = "by hand" if trigger == "manual" else "after the deploy"
    message = f"Post-deploy steps for {upgrades.label(build)} {'failed' if failed else 'done'} ({who})"
    platform_monitor.record(
        "system",
        KIND,
        message,
        level="error" if failed else "info",
        details={
            "build": build_key,
            "to": build,
            "trigger": trigger,
            "actor_id": actor_id,
            "state": overall,
            "steps": results,
        },
    )
    if failed:
        bad = next(r for r in results if r["state"] == "failed")
        platform_monitor.alert(
            upgrades.ALERT_TYPE,
            message,
            [
                f"{bad['label']} failed: {bad['output'][:300]}",
                "The steps after it did not run. Fix the cause and start them again "
                "in manage › Diagnostics › System health.",
            ],
            level="error",
            throttle=False,
        )
    return {"state": overall, "steps": results}
