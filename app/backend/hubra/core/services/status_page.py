"""The public status page: is Hubra working, for members and club admins.

Fed by what manage already watches (``platform_monitor.open_problems``,
the platform event log and maintenance), but only in coarse, public words:
three parts of Hubra, each working, limited or down, the maintenance that
is on or planned, and the outages of the last days.  No host names, error
texts or numbers leave this module.

* **app** — the club app, sign-in and the API: down while the database is
  unreachable; limited while Redis is, or while the API answers with many
  server errors or is slow.
* **mail** — mail to members: down while every configured relay is down;
  limited while one of them is, or mail skips the main relay.
* **notifications** — reminders, scheduled mails and other background jobs:
  limited while the background jobs stand still.

The live part is cached for ``CACHE_SECONDS`` per process: the page is
public and ``open_problems`` reads a few tables.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from hubra.core.extensions import db

logger = logging.getLogger(__name__)

COMPONENTS = ("app", "mail", "notifications")
LEVELS = ("operational", "degraded", "down")
CACHE_SECONDS = 30
HISTORY_DAYS = 14

_cache: dict = {}
_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _worse(a: str, b: str) -> str:
    return a if LEVELS.index(a) >= LEVELS.index(b) else b


def components_from(problems: list[dict]) -> dict[str, str]:
    """Each component's level from manage's open problems (by their id)."""
    from hubra.core.services import platform_monitor

    out = dict.fromkeys(COMPONENTS, "operational")
    ids = {p["id"] for p in problems}

    def mark(component: str, level: str) -> None:
        out[component] = _worse(out[component], level)

    if "service:db" in ids:
        mark("app", "down")
    if "service:redis" in ids:
        mark("app", "degraded")
    if ids & {"perf:errors", "perf:slow"}:
        mark("app", "degraded")

    relays_down = {i.split(":", 1)[1] for i in ids if i.startswith("relay:")} - {
        "skipped"
    }
    if relays_down:
        configured = {
            r for r in platform_monitor.RELAYS if platform_monitor._relay_config(r)
        } or {"relay"}
        mark("mail", "down" if configured <= relays_down else "degraded")
    if "relay:skipped" in ids:
        mark("mail", "degraded")

    if "jobs" in ids:
        mark("notifications", "degraded")
    return out


def _live() -> dict[str, str]:
    from hubra.core.services import platform_monitor

    with _lock:
        hit = _cache.get("live")
        if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
            return hit[1]
    try:
        live = components_from(platform_monitor.open_problems())
    except Exception:  # noqa: BLE001
        # open_problems reads the database: if that fails, the app is down.
        logger.warning("status_page_problems_failed", exc_info=True)
        db.session.rollback()
        live = {**dict.fromkeys(COMPONENTS, "operational"), "app": "down"}
    with _lock:
        _cache["live"] = (time.monotonic(), live)
    return live


def clear_cache() -> None:
    with _lock:
        _cache.clear()


# ── History ─────────────────────────────────────────────────────────────────

# platform event kind → (component, level, key in details naming the thing)
_DOWN = {
    "service.down": ("service", "service.up"),
    "relay.down": ("relay", "relay.up"),
}


def _component(kind: str, details: dict) -> tuple[str, str] | None:
    if kind == "service.down":
        svc = details.get("service")
        if svc == "db":
            return "app", "down"
        if svc == "redis":
            return "app", "degraded"
        return None
    if kind == "relay.down":
        return "mail", "degraded"
    return None


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def incidents(days: int = HISTORY_DAYS, now: datetime | None = None) -> list[dict]:
    """Outages of the last *days*, newest first: a ``*.down`` event and the
    ``*.up`` event that ended it (none while it lasts)."""
    from hubra.core.models.platform_event import PlatformEvent

    now = now or _now()
    since = now - timedelta(days=days)
    kinds = list(_DOWN) + [up for _, up in _DOWN.values()]
    events = db.session.scalars(
        select(PlatformEvent)
        .where(PlatformEvent.kind.in_(kinds), PlatformEvent.created_at >= since)
        .order_by(PlatformEvent.created_at, PlatformEvent.id)
    ).all()
    open_: dict[tuple, dict] = {}
    out: list[dict] = []
    for e in events:
        details = e.details or {}
        if e.kind in _DOWN:
            field, _ = _DOWN[e.kind]
            what = _component(e.kind, details)
            key = (e.kind, details.get(field))
            if what is None or key in open_:
                continue
            item = {
                "component": what[0],
                "level": what[1],
                "started_at": _aware(e.created_at).isoformat(),
                "ended_at": None,
            }
            open_[key] = item
            out.append(item)
        else:
            down_kind = next(k for k, (_, up) in _DOWN.items() if up == e.kind)
            field, _ = _DOWN[down_kind]
            item = open_.pop((down_kind, details.get(field)), None)
            if item is not None:
                item["ended_at"] = _aware(e.created_at).isoformat()
    out.sort(key=lambda i: i["started_at"], reverse=True)
    return out


def past_maintenance(tenant_id: int | None, days: int = HISTORY_DAYS) -> list[dict]:
    """Maintenance windows of the last *days* that covered this club."""
    from hubra.core.models.maintenance_window import MaintenanceWindow

    now = _now()
    rows = db.session.scalars(
        select(MaintenanceWindow)
        .where(
            MaintenanceWindow.cancelled_at.is_(None),
            MaintenanceWindow.ends_at >= now - timedelta(days=days),
            MaintenanceWindow.starts_at <= now,
        )
        .order_by(MaintenanceWindow.starts_at.desc())
    ).all()
    out = []
    for w in rows:
        ids = w.tenant_ids
        if ids is not None and (tenant_id is None or tenant_id not in ids):
            continue
        out.append(
            {
                "starts_at": _aware(w.starts_at).isoformat(),
                "ends_at": _aware(w.ends_at).isoformat(),
                "message": w.message or "",
            }
        )
    return out


def page(tenant_id: int | None = None) -> dict:
    """Everything the status page shows, for one club or the platform."""
    from hubra.core.services import maintenance

    components = _live()
    maint = maintenance.club_state(tenant_id)
    overall = "operational"
    for level in components.values():
        overall = _worse(overall, level)
    if maint.get("active"):
        overall = "maintenance"
    try:
        history = incidents()
        planned = past_maintenance(tenant_id)
    except Exception:  # noqa: BLE001
        logger.warning("status_page_history_failed", exc_info=True)
        db.session.rollback()
        history, planned = [], []
    return {
        "overall": overall,
        "components": [{"id": c, "level": components[c]} for c in COMPONENTS],
        "maintenance": maint,
        "incidents": history,
        "past_maintenance": planned,
        "history_days": HISTORY_DAYS,
        "checked_at": _now().isoformat(),
    }


def install(app) -> None:
    """``GET /api/v1/status`` (public; ``?club=<slug>`` for one club's
    maintenance).  Answers during maintenance too."""
    from flask import jsonify, request

    def _status():
        from hubra.core.tenant.service import TenantService

        tenant = None
        slug = (request.args.get("club") or "").strip()[:100]
        if slug:
            tenant = TenantService.get_by_slug(slug)
            if tenant is not None and tenant.status not in ("active", "suspended"):
                tenant = None
        body = page(tenant.id if tenant else None)
        body["club"] = {"slug": tenant.slug, "name": tenant.name} if tenant else None
        resp = jsonify(body)
        resp.headers["Cache-Control"] = "public, max-age=30"
        return resp, 200

    app.add_url_rule("/api/v1/status", "status_page", _status, methods=["GET"])
