"""Unexpected API errors, grouped, with the build they first happened on.

Every exception the API doesn't handle (the ones that answer 500) is
counted in an ``ErrorGroup``: same exception type, same route rule and same
place in Hubra's code is one group.  The group keeps the latest message and
traceback (Hubra's frames only, e-mail addresses masked), how often it
happened, when, and on which builds (``core/build_info``).  The first build
is the release that introduced it; manage links it to the upgrade that
brought that build (``services/upgrades``).

A new group, and a resolved one that happens again, also go to the
platform event log (``system`` / ``error.new``, ``error.regressed``).

Recording never raises and never touches the failing request's session:
it writes on its own connection (the session's on SQLite, as the platform
event log does).
"""

from __future__ import annotations

import hashlib
import logging
import re
import traceback as tb
from datetime import datetime, timezone

from sqlalchemy import insert, select, update

from hubra.core import build_info
from hubra.core.models.error_group import ErrorGroup
from hubra.core.timeutil import as_utc

logger = logging.getLogger(__name__)

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_MAX_MESSAGE = 500
_MAX_TRACEBACK = 8000
_MAX_BUILDS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _scrub(text: str) -> str:
    return _EMAIL.sub("<email>", text)


def _short_path(filename: str) -> str | None:
    """``hubra/api/members/services.py`` for a file of Hubra's, else None."""
    import os

    import hubra

    root = os.path.dirname(os.path.abspath(hubra.__file__))
    path = os.path.abspath(filename)
    if not path.startswith(root + os.sep):
        return None
    return "hubra/" + os.path.relpath(path, root).replace(os.sep, "/")


def describe(exc: BaseException) -> dict:
    """Type, location, message and traceback of *exc*, ready to store."""
    frames = tb.extract_tb(exc.__traceback__)
    own = [(f, p) for f in frames if (p := _short_path(f.filename))]
    if own:
        frame, path = own[-1]
        location = f"{path} in {frame.name}"
    else:
        location = ""
    exc_type = f"{type(exc).__module__}.{type(exc).__qualname__}".removeprefix(
        "builtins."
    )
    message = _scrub(str(exc))[:_MAX_MESSAGE]
    lines = [
        f"  {p}:{f.lineno} in {f.name}\n    {(f.line or '').strip()}" for f, p in own
    ]
    text = "\n".join(lines[-15:] + [f"{exc_type}: {message}"])
    return {
        "exc_type": exc_type[:200],
        "location": location[:300],
        "message": message,
        "traceback": text[-_MAX_TRACEBACK:],
    }


def fingerprint(exc_type: str, route: str, location: str) -> str:
    return hashlib.sha1(
        f"{exc_type}|{route}|{location}".encode(), usedforsecurity=False
    ).hexdigest()


def build_label(version: str | None, commit: str | None) -> str:
    v = version or "dev"
    return f"{v} ({commit[:7]})" if commit else v


def capture(exc: BaseException, route: str | None = None, tenant_id=None) -> None:
    """Count one unexpected error.  Never raises."""
    try:
        _capture(exc, route, tenant_id)
    except Exception:  # noqa: BLE001
        logger.warning("error_group_write_failed", exc_info=True)


def _route_and_tenant(route, tenant_id):
    if route is None:
        try:
            from hubra.core.services.perf_monitor import route_label

            route = route_label()
        except Exception:  # noqa: BLE001
            route = "(no request)"
    if tenant_id is None:
        try:
            from hubra.core.tenant.context import current_tenant

            tenant_id = getattr(current_tenant(), "id", None)
        except Exception:  # noqa: BLE001
            tenant_id = None
    return route[:300], tenant_id


def _capture(exc, route, tenant_id) -> None:
    from hubra.core.services import platform_monitor

    route, tenant_id = _route_and_tenant(route, tenant_id)
    info = describe(exc)
    fp = fingerprint(info["exc_type"], route, info["location"])
    version, commit = build_info.version(), build_info.commit()
    label = build_label(version, commit)
    now = _now()
    event = None
    with platform_monitor._connection() as conn:
        row = conn.execute(
            select(
                ErrorGroup.id,
                ErrorGroup.count,
                ErrorGroup.builds,
                ErrorGroup.status,
            ).where(ErrorGroup.fingerprint == fp)
        ).first()
        if row is None:
            conn.execute(
                insert(ErrorGroup).values(
                    fingerprint=fp,
                    route=route,
                    count=1,
                    first_seen=now,
                    last_seen=now,
                    first_version=version,
                    first_commit=commit,
                    last_version=version,
                    last_commit=commit,
                    builds={label: 1},
                    last_tenant_id=tenant_id,
                    status="open",
                    **info,
                )
            )
            event = ("error.new", f"New error: {info['exc_type']} in {route}")
        else:
            builds = dict(row.builds or {})
            builds[label] = int(builds.get(label, 0)) + 1
            if len(builds) > _MAX_BUILDS:
                builds = dict(list(builds.items())[-_MAX_BUILDS:])
            values = {
                "count": row.count + 1,
                "last_seen": now,
                "last_version": version,
                "last_commit": commit,
                "builds": builds,
                "last_tenant_id": tenant_id,
                "message": info["message"],
                "traceback": info["traceback"],
            }
            if row.status == "resolved":
                values.update(status="open", reopened_at=now)
                event = (
                    "error.regressed",
                    f"Resolved error is back: {info['exc_type']} in {route}",
                )
            conn.execute(
                update(ErrorGroup).where(ErrorGroup.id == row.id).values(**values)
            )
    if event is not None:
        platform_monitor.record(
            "system",
            event[0],
            event[1],
            level="warning",
            details={
                "fingerprint": fp,
                "type": info["exc_type"],
                "route": route,
                "location": info["location"],
                "build": label,
            },
            tenant_id=tenant_id,
        )


def install(app) -> None:
    """Count every exception Flask doesn't handle (it answers 500)."""
    from flask import got_request_exception

    def _on_exception(sender, exception, **_kw):
        capture(exception)

    got_request_exception.connect(_on_exception, app, weak=False)


# ── Reading (manage) ────────────────────────────────────────────────────────


def release_of(commit: str | None, version: str | None) -> dict | None:
    """The upgrade that brought this build, from the platform event log."""
    from hubra.core.extensions import db
    from hubra.core.models.platform_event import PlatformEvent
    from hubra.core.services import upgrades

    if not commit and not version:
        return None
    rows = db.session.scalars(
        select(PlatformEvent)
        .where(
            PlatformEvent.category == "system",
            PlatformEvent.kind.in_((upgrades.STARTED, upgrades.BASELINE)),
        )
        .order_by(PlatformEvent.created_at)
    ).all()
    for e in rows:
        to = (e.details or {}).get("to") or (e.details or {}).get("build") or {}
        if (commit and to.get("commit") == commit) or (
            not commit and version and to.get("version") == version
        ):
            return {
                "kind": e.kind,
                "at": as_utc(e.created_at).isoformat(),
                "message": e.message,
            }
    return None


def group_json(
    g: ErrorGroup, *, full: bool = False, current: str | None = None
) -> dict:
    first = build_label(g.first_version, g.first_commit)
    out = {
        "id": g.id,
        "exc_type": g.exc_type,
        "route": g.route,
        "location": g.location,
        "message": g.message,
        "count": g.count,
        "first_seen": as_utc(g.first_seen).isoformat(),
        "last_seen": as_utc(g.last_seen).isoformat(),
        "first_build": first,
        "first_commit": g.first_commit,
        "last_build": build_label(g.last_version, g.last_commit),
        "builds": g.builds or {},
        "status": g.status,
        "resolved_at": as_utc(g.resolved_at).isoformat() if g.resolved_at else None,
        "reopened_at": as_utc(g.reopened_at).isoformat() if g.reopened_at else None,
        "last_tenant_id": g.last_tenant_id,
        "new_in_current": current is not None and first == current,
    }
    if full:
        out["traceback"] = g.traceback
        out["release"] = release_of(g.first_commit, g.first_version)
    return out


def current_build() -> str:
    return build_label(build_info.version(), build_info.commit())
