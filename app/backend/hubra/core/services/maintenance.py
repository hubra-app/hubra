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
with ``flask maintenance off``, or in manage › Platform › Alerts.

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
    "/api/v1/manager",
    "/api/v1/system",
    "/api/v1/auth",
    "/api/v1/account",
    "/api/v1/apps",  # outside callbacks (Discord interactions, OAuth)
    "/api/v1/i18n",
    "/api/v1/instance",  # public instance info the apps need to start
)


def _parse(value: str) -> datetime | None:
    if not value:
        return None
    try:
        at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def state(fresh: bool = False) -> dict:
    """``{"active", "message", "until"}``.  Never raises: without the
    database the platform is not in maintenance."""
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
    active = enabled and (until is None or until > datetime.now(timezone.utc))
    result = {
        "active": active,
        "message": message if active else "",
        "until": until.isoformat() if active and until else None,
    }
    _cache.update(at=now, state=result)
    return result


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
    return state(fresh=True)


def turn_off(actor_id=None) -> dict:
    from hubra.core.extensions import db
    from hubra.core.services import platform_settings

    platform_settings.set_many(
        {"maintenance.enabled": None, "maintenance.until": None}, actor_id=actor_id
    )
    db.session.commit()
    clear_cache()
    _log_event("Maintenance mode off")
    return state(fresh=True)


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
        return jsonify(state()), 200

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
