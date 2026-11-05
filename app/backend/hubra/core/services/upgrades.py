"""Upgrades: notice when a new build rolls out and when every process runs it.

Every backend process reports its commit and version (``core/build_info.py``).
The beat task ``upgrade_tasks.check_upgrades`` compares those reports with the
last upgrade event in the platform event log (category ``system``):

* ``upgrade.baseline``: the first check on an install remembers what runs.
  No alert.
* ``upgrade.started``: a process runs a build other than the remembered one.
  Alert type ``upgrades`` (mail to platform admins who keep it on, and the
  platform Discord log).
* ``upgrade.done``: every reporting process runs the new build.  Alert with
  how long the roll-out took.
* ``upgrade.stuck``: still not done after ``STUCK_AFTER``; one warning, naming
  the processes left on another build.

A build is told apart by its commit, or by its version for builds without one
(local and dev builds).  The log itself is the state, so nothing new is
stored, and a Redis flush can't cause a false alarm.  A stopped process drops
out of the reports after a minute or two, so "done" can come that much after
the last old pod is gone.
"""

from __future__ import annotations

import logging
import os
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from hubra.core import build_info
from hubra.core.extensions import db
from hubra.core.models.platform_event import PlatformEvent
from hubra.core.timeutil import as_utc

logger = logging.getLogger(__name__)

BASELINE = "upgrade.baseline"
STARTED = "upgrade.started"
DONE = "upgrade.done"
STUCK = "upgrade.stuck"
_STATE_KINDS = (BASELINE, STARTED, DONE)
STUCK_AFTER = timedelta(minutes=30)
ALERT_TYPE = "upgrades"


def _key(build: dict) -> str:
    return build.get("commit") or f"v{build.get('version')}"


def label(build: dict) -> str:
    """``0.3.0 (abc1234)``, or just the version for a build without a commit."""
    version = build.get("version") or "?"
    commit = build.get("commit")
    return f"{version} ({commit[:7]})" if commit else version


def _build(entry: dict) -> dict:
    return {"commit": entry.get("commit"), "version": entry.get("version")}


def _processes() -> list[dict] | None:
    """What every process runs; None when Redis is set up but did not
    answer (then nothing is known, rather than only this worker)."""
    reports = build_info.read_reports()
    if reports is None:
        return None
    if reports:
        return reports
    # No Redis: this worker is all we know about.
    return [
        {
            "component": "worker",
            "host": os.environ.get("HOSTNAME") or "local",
            "commit": build_info.commit(),
            "version": build_info.version(),
        }
    ]


def _most_common(entries: list[dict]) -> dict:
    counts = Counter(_key(e) for e in entries)
    top = counts.most_common(1)[0][0]
    return _build(next(e for e in entries if _key(e) == top))


def _who(entries: list[dict]) -> str:
    return ", ".join(f"{e.get('component')}@{e.get('host')}" for e in entries)


def last_event() -> PlatformEvent | None:
    """The newest baseline/started/done event, or None on a fresh install."""
    return db.session.execute(
        select(PlatformEvent)
        .where(PlatformEvent.category == "system")
        .where(PlatformEvent.kind.in_(_STATE_KINDS))
        .order_by(PlatformEvent.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def _stuck_reported_since(when: datetime) -> bool:
    return (
        db.session.execute(
            select(PlatformEvent.id)
            .where(PlatformEvent.category == "system")
            .where(PlatformEvent.kind == STUCK)
            .where(PlatformEvent.created_at >= when)
            .limit(1)
        ).first()
        is not None
    )


def _start(old: dict, new: dict, procs: list[dict], *, notify: bool = True) -> None:
    from hubra.core.services import platform_monitor

    message = f"Upgrade started: {label(old)} → {label(new)}"
    platform_monitor.record(
        "system", STARTED, message, details={"from": old, "to": new}
    )
    if notify:
        behind = [p for p in procs if _key(p) != _key(new)]
        lines = [f"From {label(old)} to {label(new)}."]
        if behind:
            lines.append(f"Still on another build: {_who(behind)}.")
        lines.append("See manage › Diagnostics › System health.")
        platform_monitor.alert(ALERT_TYPE, message, lines, level="info", throttle=False)


def _finish(old: dict, new: dict, started_at: datetime | None) -> None:
    from hubra.core.services import platform_monitor

    minutes = None
    if started_at is not None:
        minutes = max(0, round((datetime.now(timezone.utc) - as_utc(started_at)).total_seconds() / 60))
    message = f"Upgrade completed: {label(old)} → {label(new)}"
    platform_monitor.record(
        "system",
        DONE,
        message,
        details={"from": old, "to": new, "minutes": minutes},
    )
    lines = [f"Every backend process now runs {label(new)}."]
    if minutes is not None:
        lines.append(f"The roll-out took about {minutes} min.")
    platform_monitor.alert(ALERT_TYPE, message, lines, level="info", throttle=False)


def check() -> dict:
    """Compare what runs with the last upgrade event; log and alert changes."""
    from hubra.core.services import platform_monitor

    procs = _processes()
    if procs is None:
        return {"state": "unknown"}
    last = last_event()
    if last is None:
        now = _most_common(procs)
        platform_monitor.record(
            "system", BASELINE, f"Running {label(now)}", details={"to": now}
        )
        return {"state": "baseline", "build": now}

    details = last.details or {}
    target = details.get("to") or {}
    others = [p for p in procs if _key(p) != _key(target)]

    if last.kind in (BASELINE, DONE):
        if not others:
            return {"state": "steady", "build": target}
        new = _most_common(others)
        if all(_key(p) == _key(new) for p in procs):
            # Rolled out completely between two checks: one message, not two.
            _start(target, new, procs, notify=False)
            _finish(target, new, None)
            return {"state": "done", "build": new}
        _start(target, new, procs)
        return {"state": "started", "build": new}

    # An upgrade is under way (last.kind == STARTED).
    old = details.get("from") or {}
    if not others:
        _finish(old, target, last.created_at)
        return {"state": "done", "build": target}
    newer = [p for p in others if _key(p) != _key(old)]
    if newer:
        # Yet another build arrived before this one finished.
        new = _most_common(newer)
        _start(target, new, procs)
        return {"state": "started", "build": new}
    started_at = as_utc(last.created_at)
    if datetime.now(timezone.utc) - started_at > STUCK_AFTER and not _stuck_reported_since(
        started_at
    ):
        minutes = round(STUCK_AFTER.total_seconds() / 60)
        message = f"Upgrade to {label(target)} not finished after {minutes} min"
        platform_monitor.record(
            "system",
            STUCK,
            message,
            level="warning",
            details={"from": old, "to": target, "behind": _who(others).split(", ")},
        )
        platform_monitor.alert(
            ALERT_TYPE,
            message,
            [f"Still on {label(old)}: {_who(others)}.", "See manage › Diagnostics › System health."],
            level="warning",
            throttle=False,
        )
        return {"state": "stuck", "build": target}
    return {"state": "rolling", "build": target}


def last_upgrade() -> dict | None:
    """The newest upgrade event for manage, or None."""
    try:
        event = db.session.execute(
            select(PlatformEvent)
            .where(PlatformEvent.category == "system")
            .where(PlatformEvent.kind.in_((STARTED, DONE, STUCK)))
            .order_by(PlatformEvent.id.desc())
            .limit(1)
        ).scalar_one_or_none()
    except Exception:
        logger.debug("last_upgrade_failed", exc_info=True)
        return None
    return event.to_dict() if event else None
