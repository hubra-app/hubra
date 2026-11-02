"""Maintenance mode for the whole platform.

While it is on (platform setting ``maintenance.enabled``, optionally ending
by itself at ``maintenance.until``):

* the club apps' API answers ``503 MAINTENANCE`` with the message and the
  expected end, and the club app shows a maintenance page instead;
* manage, sign-in, the account pages, health checks and outside callbacks
  keep working, so platform staff can check the release;
* alert mails and Discord alerts are paused (the event log still keeps
  every event), and server errors are not counted for the error-rate alert.

Turn it on around a release with ``flask maintenance on --minutes 15`` and off
with ``flask maintenance off``, or in manage › Alerts.

Planned maintenance (``MaintenanceWindow``, manage › Maintenance ›
Geplante Wartungen): a start and end for every club or for some clubs.
While a window runs, the clubs it covers get the same 503 and page; a window
for every club counts as maintenance mode (alerts pause too).  From
``notice_hours`` before the start, ``GET /api/v1/maintenance`` names the
window under ``upcoming`` and the club app shows a notice.

The state is read from the database at most every few seconds per process,
so every request does not cost a query.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request

logger = logging.getLogger(__name__)

_CACHE_SECONDS = 5.0
_cache: dict = {"at": 0.0, "state": None}

# Requests that keep working during maintenance.
ALLOWED_PREFIXES = (
    "/health",
    "/api/v1/health",
    "/api/v1/maintenance",
    "/api/v1/status",
    "/api/v1/manager",
    "/api/v1/system",
    "/api/v1/auth",
    "/api/v1/account",
    "/api/v1/apps",  # outside callbacks (OAuth)
    # Signed Discord interactions: /wartung ende must work during maintenance;
    # club commands answer with the maintenance notice themselves.
    "/api/v1/discord/interactions",
    "/api/v1/i18n",
    "/api/v1/instance",  # public instance info the apps need to start
    "/api/v1/public",  # pricing and plugin list for the website
)


def _parse(value: str) -> datetime | None:
    if not value:
        return None
    try:
        at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def _window_dict(w) -> dict:
    return {
        "id": w.id,
        "starts_at": w.starts_at
        if w.starts_at.tzinfo
        else w.starts_at.replace(tzinfo=timezone.utc),
        "ends_at": w.ends_at
        if w.ends_at.tzinfo
        else w.ends_at.replace(tzinfo=timezone.utc),
        "message": w.message or "",
        "tenant_ids": list(w.tenant_ids) if w.tenant_ids is not None else None,
        "notice_hours": w.notice_hours,
    }


def _load(fresh: bool) -> dict:
    """Maintenance mode's settings and the windows that have not ended,
    cached for a few seconds per process."""
    now = time.monotonic()
    if (
        not fresh
        and _cache["state"] is not None
        and now - _cache["at"] < _CACHE_SECONDS
    ):
        return _cache["state"]
    try:
        from hubra.core.services import platform_settings

        enabled = platform_settings.get("maintenance.enabled") == "on"
        until = _parse(platform_settings.get("maintenance.until"))
        message = platform_settings.get("maintenance.message")
    except Exception:  # noqa: BLE001
        logger.debug("maintenance state unreadable", exc_info=True)
        enabled, until, message = False, None, ""
    try:
        windows = [_window_dict(w) for w in _open_windows()]
    except Exception:  # noqa: BLE001
        logger.debug("maintenance windows unreadable", exc_info=True)
        windows = []
    loaded = {
        "enabled": enabled,
        "until": until,
        "message": message,
        "windows": windows,
    }
    _cache.update(at=now, state=loaded)
    return loaded


def _open_windows():
    from sqlalchemy import select

    from hubra.core.extensions import db
    from hubra.core.models.maintenance_window import MaintenanceWindow

    return db.session.scalars(
        select(MaintenanceWindow)
        .where(
            MaintenanceWindow.cancelled_at.is_(None),
            MaintenanceWindow.ends_at > datetime.now(timezone.utc),
        )
        .order_by(MaintenanceWindow.starts_at)
    ).all()


def _covers(window: dict, tenant_id: int | None) -> bool:
    ids = window["tenant_ids"]
    return ids is None or (tenant_id is not None and tenant_id in ids)


def _running(window: dict, now: datetime) -> bool:
    return window["starts_at"] <= now < window["ends_at"]


def _active_from(window: dict) -> dict:
    return {
        "active": True,
        "message": window["message"],
        "until": window["ends_at"].isoformat(),
        "window_id": window["id"],
    }


def state(fresh: bool = False) -> dict:
    """``{"active", "message", "until"}`` for the whole platform: maintenance
    mode, or a window for every club that is running.  Never raises: without
    the database the platform is not in maintenance."""
    loaded = _load(fresh)
    now = datetime.now(timezone.utc)
    until = loaded["until"]
    if loaded["enabled"] and (until is None or until > now):
        return {
            "active": True,
            "message": loaded["message"],
            "until": until.isoformat() if until else None,
        }
    for w in loaded["windows"]:
        if w["tenant_ids"] is None and _running(w, now):
            return _active_from(w)
    return {"active": False, "message": "", "until": None}


def club_state(tenant_id: int | None, fresh: bool = False) -> dict:
    """:func:`state` for one club: also its own windows, and the next window
    that covers it once its notice period has started (``upcoming``)."""
    current = state(fresh)
    now = datetime.now(timezone.utc)
    windows = [w for w in _load(False)["windows"] if _covers(w, tenant_id)]
    if not current["active"]:
        running = next((w for w in windows if _running(w, now)), None)
        if running is not None:
            current = _active_from(running)
    upcoming = next(
        (
            w
            for w in windows
            if w["starts_at"] > now
            and w["starts_at"] - timedelta(hours=w["notice_hours"]) <= now
        ),
        None,
    )
    return {
        **current,
        "upcoming": {
            "id": upcoming["id"],
            "starts_at": upcoming["starts_at"].isoformat(),
            "ends_at": upcoming["ends_at"].isoformat(),
            "message": upcoming["message"],
        }
        if upcoming
        else None,
    }


def is_active() -> bool:
    return state()["active"]


def clear_cache() -> None:
    _cache.update(at=0.0, state=None)


def turn_on(message: str = "", minutes: int | None = None, actor_id=None) -> dict:
    from hubra.core.extensions import db
    from hubra.core.services import platform_settings

    until = (
        (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat(
            timespec="minutes"
        )
        if minutes
        else None
    )
    platform_settings.set_many(
        {
            "maintenance.enabled": "on",
            "maintenance.message": message or None,
            "maintenance.until": until,
        },
        actor_id=actor_id,
    )
    db.session.commit()
    clear_cache()
    _log_event(f"Maintenance mode on{' until ' + until if until else ''}")
    current = state(fresh=True)
    _notify_clubs("maintenance_started", notice_payload(current))
    return current


def turn_off(actor_id=None) -> dict:
    """End maintenance mode, and any running window for every club."""
    from hubra.core.extensions import db
    from hubra.core.services import platform_settings

    # Windows that end here are announced by the platform bot's tick.
    was_on = _load(True)["enabled"]

    platform_settings.set_many(
        {"maintenance.enabled": None, "maintenance.until": None}, actor_id=actor_id
    )
    now = datetime.now(timezone.utc)
    for w in _open_windows():
        starts = (
            w.starts_at
            if w.starts_at.tzinfo
            else w.starts_at.replace(tzinfo=timezone.utc)
        )
        if w.tenant_ids is None and starts <= now:
            w.ends_at = now
    db.session.commit()
    clear_cache()
    _log_event("Maintenance mode off")
    if was_on:
        _notify_clubs("maintenance_ended", {})
    return state(fresh=True)


# ── Planned windows ─────────────────────────────────────────────────────────

MAX_WINDOW = timedelta(days=7)
NOTICE_HOURS = (0, 24, 48, 72, 168)


class WindowError(ValueError):
    pass


def _aware(at: datetime) -> datetime:
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def window_json(w, names: dict[int, str] | None = None) -> dict:
    now = datetime.now(timezone.utc)
    starts, ends = _aware(w.starts_at), _aware(w.ends_at)
    if w.cancelled_at is not None:
        status = "cancelled"
    elif ends <= now:
        status = "done"
    elif starts <= now:
        status = "running"
    elif starts - timedelta(hours=w.notice_hours) <= now:
        status = "announced"
    else:
        status = "planned"
    ids = list(w.tenant_ids) if w.tenant_ids is not None else None
    return {
        "id": w.id,
        "starts_at": starts.isoformat(),
        "ends_at": ends.isoformat(),
        "message": w.message or "",
        "tenant_ids": ids,
        "clubs": [{"id": i, "name": (names or {}).get(i)} for i in ids]
        if ids is not None
        else None,
        "notice_hours": w.notice_hours,
        "status": status,
        "created_by": w.created_by,
        "created_at": _aware(w.created_at).isoformat() if w.created_at else None,
        "cancelled_at": _aware(w.cancelled_at).isoformat() if w.cancelled_at else None,
    }


def schedule(
    starts_at: datetime,
    ends_at: datetime,
    message: str = "",
    tenant_ids: list[int] | None = None,
    notice_hours: int = 24,
    actor_id=None,
):
    """Plan a window.  ``tenant_ids`` None: every club.  Commits."""
    from sqlalchemy import select

    from hubra.core.extensions import db
    from hubra.core.models.maintenance_window import MaintenanceWindow
    from hubra.core.models.tenant import Tenant

    starts_at, ends_at = _aware(starts_at), _aware(ends_at)
    if ends_at <= starts_at:
        raise WindowError("The end must be after the start")
    if ends_at <= datetime.now(timezone.utc):
        raise WindowError("The end is in the past")
    if ends_at - starts_at > MAX_WINDOW:
        raise WindowError("A window is at most 7 days long")
    if notice_hours not in NOTICE_HOURS:
        raise WindowError(f"notice_hours is one of {list(NOTICE_HOURS)}")
    if len(message) > 500:
        raise WindowError("The message is at most 500 characters")
    if tenant_ids is not None:
        tenant_ids = sorted(set(tenant_ids))
        if not tenant_ids:
            raise WindowError("Pick at least one club, or every club")
        found = set(
            db.session.scalars(
                select(Tenant.id).where(
                    Tenant.id.in_(tenant_ids), Tenant.deleted_at.is_(None)
                )
            )
        )
        if missing := [i for i in tenant_ids if i not in found]:
            raise WindowError(f"Unknown clubs: {missing}")
    window = MaintenanceWindow(
        starts_at=starts_at,
        ends_at=ends_at,
        message=message,
        tenant_ids=tenant_ids,
        notice_hours=notice_hours,
        created_by=actor_id,
    )
    db.session.add(window)
    db.session.commit()
    clear_cache()
    who = "every club" if tenant_ids is None else f"{len(tenant_ids)} club(s)"
    _log_event(
        f"Maintenance planned for {who}: "
        f"{starts_at.isoformat(timespec='minutes')} to {ends_at.isoformat(timespec='minutes')}"
    )
    _notify_clubs("maintenance_planned", window_notice(window))
    return window


def cancel(window_id: int, actor_id=None):
    """Cancel a planned window, or end a running one now.  Commits."""
    from hubra.core.extensions import db
    from hubra.core.models.maintenance_window import MaintenanceWindow

    window = db.session.get(MaintenanceWindow, window_id)
    if window is None:
        raise LookupError(window_id)
    now = datetime.now(timezone.utc)
    if window.cancelled_at is not None or _aware(window.ends_at) <= now:
        raise WindowError("This window is already over")
    if _aware(window.starts_at) <= now:
        window.ends_at = now
        _log_event(f"Maintenance window {window.id} ended early")
    else:
        window.cancelled_at = now
        window.cancelled_by = actor_id
        _log_event(f"Maintenance window {window.id} cancelled")
        _notify_clubs(
            "maintenance_cancelled", {"tenant_ids": window_notice(window)["tenant_ids"]}
        )
    db.session.commit()
    clear_cache()
    return window


# ── Notices on the clubs' Discord servers ─────────────────────────────────────


def notice_payload(current: dict) -> dict:
    """What the clubs' Discord servers are told when maintenance starts."""
    return {"message": current.get("message") or "", "until": current.get("until")}


def window_notice(window) -> dict:
    """A planned window, for the clubs' Discord servers (``tenant_ids`` None:
    every club)."""
    starts, ends = _aware(window.starts_at), _aware(window.ends_at)
    return {
        "message": window.message or "",
        "start": starts.isoformat(),
        "until": ends.isoformat(),
        "minutes": int((ends - starts).total_seconds() // 60),
        "tenant_ids": list(window.tenant_ids) if window.tenant_ids is not None else None,
    }


def _notify_clubs(kind: str, payload: dict) -> None:
    """Club Discord servers that opted in hear about maintenance (after the
    commit, in the background).  Never raises."""
    try:
        from hubra.core.services import platform_bot

        platform_bot.notify_clubs(kind, payload)
    except Exception:  # noqa: BLE001
        logger.debug("maintenance club notice skipped", exc_info=True)


def _log_event(message: str) -> None:
    try:
        from hubra.core.services import platform_monitor

        platform_monitor.record("system", "system.maintenance", message, level="info")
    except Exception:  # noqa: BLE001
        logger.debug("maintenance event not logged", exc_info=True)


def install(app: Flask) -> None:
    """Answer the club apps' API with 503 while maintenance is on, and serve
    ``GET /api/v1/maintenance`` (public) so the club app can show the notice."""

    def _public_state():
        from hubra.core.tenant.context import current_tenant

        tenant = current_tenant()
        return jsonify(club_state(tenant.id if tenant else None)), 200

    app.add_url_rule(
        "/api/v1/maintenance", "maintenance_state", _public_state, methods=["GET"]
    )

    @app.before_request
    def _maintenance_gate():
        path = request.path
        if not path.startswith("/api/") or path.startswith(ALLOWED_PREFIXES):
            return None
        if request.method == "OPTIONS":
            return None
        current = state()
        if not current["active"]:
            return None
        from flask import g

        g.maintenance = True
        resp = jsonify(
            {
                "error": "MAINTENANCE",
                "message": current["message"]
                or "Hubra is being updated. Please try again shortly.",
                "until": current["until"],
            }
        )
        resp.status_code = 503
        resp.headers["Retry-After"] = "120"
        return resp


def install_club_gate(app: Flask) -> None:
    """The same 503 for a club while one of its own windows runs.  Needs the
    club, so it is registered after ``resolve_tenant``."""

    @app.before_request
    def _club_window_gate():
        path = request.path
        if not path.startswith("/api/") or path.startswith(ALLOWED_PREFIXES):
            return None
        if request.method == "OPTIONS":
            return None
        from flask import g

        tenant = getattr(g, "tenant", None)
        if tenant is None or getattr(g, "maintenance", False):
            return None
        current = club_state(tenant.id)
        if not current["active"]:
            return None
        g.maintenance = True
        resp = jsonify(
            {
                "error": "MAINTENANCE",
                "message": current["message"]
                or "Hubra is being updated. Please try again shortly.",
                "until": current["until"],
            }
        )
        resp.status_code = 503
        resp.headers["Retry-After"] = "120"
        return resp
