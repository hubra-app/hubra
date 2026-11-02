"""Platform settings for the manager portal.

``platform_bp`` (``/api/v1/manager/platform``): instance-wide settings such as the outbound
mail relay, which need the global permission ``platform.settings``, and the
diagnostics of the whole instance (system health, the outbound mail relays
and the platform event log, the shared mail server, the API permission
table), which need ``platform.diagnostics`` to look at and
``platform.settings`` to change anything.
"""

from __future__ import annotations

import re
import time

from flask import Blueprint, g, jsonify, request

from hubra.api.auth.account_token import require_step_up
from hubra.api.permissions import require_global_permission
from hubra.core.errors import api_error
from hubra.core.extensions import db, limiter
from hubra.core.models.tenant import GlobalAuditEntry
from hubra.core.services import email, mail_server, platform_monitor, platform_settings
from hubra.core.services.platform_settings import PlatformSettingError

platform_bp = Blueprint("platform_bp", __name__)

_PERM = "platform.settings"
_DIAGNOSTICS = "platform.diagnostics"
_STALE_THRESHOLD = 60  # seconds — 3× the 20s beat interval
_OBJECTID_RE = re.compile(r"^[0-9a-fA-F]{24}$")


def _audit(action: str, target_type: str, target_id: str, details: dict | None = None):
    actor = getattr(g, "system_user", None)
    db.session.add(
        GlobalAuditEntry(
            tenant_id=None,
            actor_id=getattr(actor, "id", None),
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details or {},
            ip_address=request.remote_addr,
        )
    )


@platform_bp.get("/settings")
@require_global_permission(_PERM)
def list_settings():
    """Every platform setting with its value and where it comes from."""
    return jsonify({"settings": platform_settings.as_list()}), 200


@platform_bp.patch("/settings")
@require_global_permission(_PERM)
def update_settings():
    """Body: ``{"<key>": "<value>" | null, ...}``.  ``null`` resets to the env default."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not body:
        return api_error("VALIDATION_ERROR", "Expected an object of settings", 400)

    actor = getattr(g, "system_user", None)
    try:
        platform_settings.set_many(body, actor_id=getattr(actor, "id", None))
    except PlatformSettingError as exc:
        details = exc.args[0]
        response = jsonify(
            {
                "error": "VALIDATION_ERROR",
                "message": "Invalid platform settings",
                "details": details if isinstance(details, dict) else {},
            }
        )
        response.status_code = 400
        return response

    db.session.add(
        GlobalAuditEntry(
            tenant_id=None,
            actor_id=getattr(actor, "id", None),
            action="platform.settings.update",
            target_type="platform_setting",
            target_id=",".join(sorted(body)),
            details={
                k: ("***" if platform_settings.spec(k).secret and v else v)
                for k, v in body.items()
            },
            ip_address=request.remote_addr,
        )
    )
    db.session.commit()
    return jsonify({"settings": platform_settings.as_list()}), 200


@platform_bp.post("/mail/test")
@require_global_permission(_PERM)
@limiter.limit("10 per hour")
def send_test_mail():
    """Send a test mail from the system sender through the relay, or with
    ``via: "fallback"`` through the fallback relay, never both."""
    body = request.get_json(silent=True) or {}
    to = str(body.get("to") or "").strip()
    if "@" not in to:
        return api_error("VALIDATION_ERROR", "'to' must be an email address", 400)
    via = str(body.get("via") or "relay")
    if via not in ("relay", "fallback"):
        return api_error("VALIDATION_ERROR", "'via' must be relay or fallback", 400)

    relay = platform_settings.relay()
    host = (
        relay.host
        if via == "relay"
        else getattr(platform_settings.fallback_relay(), "host", "")
    )
    if not host or not relay.sender_email:
        return api_error(
            "SERVICE_UNAVAILABLE",
            "Set the relay host and the system sender address first",
            503,
        )
    try:
        email._send_via_smtp(
            to,
            to,
            relay.sender_email,
            relay.sender_name,
            "Hubra test mail",
            "<p>This is a test mail from your Hubra platform relay.</p>",
            "This is a test mail from your Hubra platform relay.",
            via=via,
        )
    except email.EmailDeliveryError as exc:
        return api_error("SMTP_ERROR", f"The relay refused the mail: {exc}", 502)
    return jsonify({"ok": True, "to": to}), 200


@platform_bp.post("/discord/test")
@require_global_permission(_PERM)
@limiter.limit("10 per hour")
def send_test_discord():
    """Post a test message to the platform log channel with the bot."""
    from hubra.core.services import platform_discord

    actor = getattr(g, "system_user", None)
    try:
        platform_discord.post(
            {
                "title": "Hubra platform log",
                "description": "Test message: the bot can post here.",
                "color": platform_discord.COLOR_INFO,
                "footer": {
                    "text": f"Sent by {getattr(actor, 'email', 'a platform admin')}"
                },
            }
        )
    except platform_discord.DiscordPostError as exc:
        return api_error("DISCORD_ERROR", str(exc), 502)
    return jsonify({"ok": True}), 200


# ── Diagnostics ───────────────────────────────────────────────────────────────


@platform_bp.get("/health")
@require_global_permission(_DIAGNOSTICS)
@limiter.exempt
def health_detailed():
    """Every service check with latencies, run now, plus the version.

    ``stale`` is true when the beat task that caches the public ``/health``
    status has not run for a while.  Always 200: this is for people, and the
    overall state is in ``status`` (load balancers use the public ``/health``).
    """
    from hubra.api.health.cache import HealthCache
    from hubra.api.health.services import HealthService
    from hubra.api.version.services import VersionService
    from hubra.core import build_info
    from hubra.core.services import upgrades

    payload = HealthService.run_all_checks()
    payload["version"] = VersionService.get_version()
    # The commit each backend process runs: this API process, plus what the
    # worker, beat and Discord gateway reported (hubra.core.build_info).
    payload["commit"] = build_info.commit()
    payload["processes"] = build_info.reported()
    payload["last_upgrade"] = upgrades.last_upgrade()

    cached = HealthCache.get()
    if cached is not None and "checked_at" in cached:
        payload["stale"] = time.time() - cached["checked_at"] > _STALE_THRESHOLD
        payload["checked_at"] = cached["checked_at"]
    else:
        payload["stale"] = True
    return jsonify(payload), 200


@platform_bp.get("/discord/status")
@require_global_permission(_DIAGNOSTICS)
def discord_status():
    """The Discord bot: settings, sign-in, platform log, club servers."""
    from hubra.core.services import discord_status as svc

    return jsonify(svc.status()), 200


@platform_bp.post("/discord/check")
@require_global_permission(_DIAGNOSTICS)
@limiter.limit("30 per hour")
def discord_check():
    """Ask Discord again now instead of using the last check."""
    from hubra.core.services import discord_status as svc

    return jsonify(svc.status(refresh=True)), 200


@platform_bp.get("/discord/servers")
@require_global_permission(_PERM)
def discord_servers():
    """The servers the bot is on, for picking the platform log server."""
    from hubra.core.services import discord_status as svc

    try:
        return jsonify(svc.servers()), 200
    except svc.PickerError as exc:
        return api_error("DISCORD_UNAVAILABLE", str(exc), 409)


@platform_bp.get("/discord/servers/<string:guild_id>/channels")
@require_global_permission(_PERM)
def discord_server_channels(guild_id: str):
    """Text channels on one of the bot's servers that the bot can post in."""
    from hubra.core.services import discord_status as svc

    try:
        return jsonify({"channels": svc.channels(guild_id)}), 200
    except svc.PickerError as exc:
        return api_error("DISCORD_UNAVAILABLE", str(exc), 409)


@platform_bp.get("/permissions")
@require_global_permission(_DIAGNOSTICS)
def list_permissions():
    """Every club API endpoint that a club permission guards, by path and method."""
    from hubra.api.system.services import SystemService

    return jsonify(SystemService.list_permissions()), 200


@platform_bp.get("/mail-server")
@require_global_permission(_DIAGNOSTICS)
def mail_server_live():
    """Every mailbox and alias on the shared mail server, with its club."""
    return jsonify({"data": mail_server.live()}), 200


@platform_bp.delete("/mail-server/<string:entry_type>/<string:entry_id>")
@require_global_permission(_PERM)
def mail_server_delete_orphan(entry_type: str, entry_id: str):
    """Delete a mailbox or alias that no club manages."""
    if entry_type not in ("mailbox", "alias"):
        return api_error("VALIDATION_ERROR", "Type must be 'mailbox' or 'alias'", 400)
    if not _OBJECTID_RE.match(entry_id):
        return api_error("VALIDATION_ERROR", f"Invalid ID format: {entry_id!r}", 400)

    label = mail_server.delete_orphan(entry_type, entry_id)
    _audit(
        f"platform.mail_server.delete_{entry_type}",
        f"wildduck_{entry_type}",
        entry_id,
        {"address": label},
    )
    db.session.commit()
    return jsonify({"ok": True, "type": entry_type, "id": entry_id}), 200


@platform_bp.post("/mail-server/reconcile")
@require_global_permission(_PERM)
@limiter.limit("10 per hour")
def mail_server_reconcile():
    """Reconcile every club's addresses with the mail server now."""
    from hubra.core.tasks.mail_tasks import reconcile_mail

    reconcile_mail.delay()
    return jsonify({"ok": True, "task": "reconcile_mail"}), 202


# ── Outbound mail: relay checks, the event log, alert choices ──────────────


def _relay_summary(which: str) -> dict:
    if which == "fallback":
        cfg = platform_settings.fallback_relay()
    else:
        cfg = platform_settings.relay()
        cfg = cfg if cfg.host else None
    return {
        "which": which,
        "configured": cfg is not None,
        "host": getattr(cfg, "host", ""),
        "port": getattr(cfg, "port", None),
        "login": bool(cfg and cfg.user and cfg.password),
        "last_check": platform_monitor.last_check(which),
    }


@platform_bp.get("/mail-relay")
@require_global_permission(_DIAGNOSTICS)
def mail_relay_status():
    """Both relays with their last check, whether mail skips the main relay
    right now, and the last 24 hours of sent, fallback and failed mail."""
    return jsonify(
        {
            "relays": [_relay_summary(w) for w in platform_monitor.RELAYS],
            "primary_down": platform_monitor.primary_down(),
            "stats": platform_monitor.stats(24),
            "check_every_minutes": 5,
        }
    ), 200


@platform_bp.post("/mail-relay/check")
@require_global_permission(_DIAGNOSTICS)
@limiter.limit("30 per hour")
def mail_relay_check():
    """Body ``{"which": "relay" | "fallback"}`` (both if left out): log in to
    the relay now, without sending a mail."""
    which = (request.get_json(silent=True) or {}).get("which")
    if which is not None and which not in platform_monitor.RELAYS:
        return api_error("VALIDATION_ERROR", "'which' must be relay or fallback", 400)
    targets = [which] if which else list(platform_monitor.RELAYS)
    results = [platform_monitor.run_check(w) for w in targets]
    return jsonify({"results": results}), 200


@platform_bp.post("/mail-relay/use-main")
@require_global_permission(_PERM)
def mail_relay_use_main():
    """Try the main relay again for the next mail, instead of waiting for
    the 15 minutes after a fallback to run out (e.g. after fixing a quota)."""
    platform_monitor.clear_primary_down()
    _audit("platform.mail_relay.use_main", "platform_setting", "mail.relay")
    db.session.commit()
    return jsonify({"primary_down": platform_monitor.primary_down()}), 200


@platform_bp.get("/events")
@require_global_permission(_DIAGNOSTICS)
def list_platform_events():
    """The platform event log, newest first.

    Query: ``category`` (mail, relay, service, backup, plugin, system,
    alert), ``level`` (info,
    warning, error, or ``problems`` for both), ``kind``, ``tenant_id`` (one
    club's events), ``q`` (text in the message), ``page``, ``per_page``
    (max 100).
    """
    from sqlalchemy import func, select

    from hubra.core.models.platform_event import CATEGORIES, LEVELS, PlatformEvent

    args = request.args
    query = select(PlatformEvent)
    category = args.get("category") or None
    level = args.get("level") or None
    if category and category not in CATEGORIES:
        return api_error("VALIDATION_ERROR", "Unknown category", 400)
    if level == "problems":
        query = query.where(PlatformEvent.level.in_(("warning", "error")))
        level = None
    elif level and level not in LEVELS:
        return api_error("VALIDATION_ERROR", "Unknown level", 400)
    if category:
        query = query.where(PlatformEvent.category == category)
    if level:
        query = query.where(PlatformEvent.level == level)
    if kind := args.get("kind"):
        query = query.where(PlatformEvent.kind == kind)
    if tenant_id := args.get("tenant_id"):
        if not tenant_id.isdigit():
            return api_error("VALIDATION_ERROR", "tenant_id must be a number", 400)
        query = query.where(PlatformEvent.tenant_id == int(tenant_id))
    if q := (args.get("q") or "").strip():
        query = query.where(PlatformEvent.message.ilike(f"%{q[:100]}%"))
    try:
        page = max(1, int(args.get("page", 1)))
        per_page = min(100, max(1, int(args.get("per_page", 25))))
    except ValueError:
        return api_error("VALIDATION_ERROR", "page and per_page must be numbers", 400)

    total = db.session.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.session.scalars(
        query.order_by(PlatformEvent.created_at.desc(), PlatformEvent.id.desc())
        .limit(per_page)
        .offset((page - 1) * per_page)
    ).all()

    from hubra.core.models.tenant import Tenant

    ids = {r.tenant_id for r in rows if r.tenant_id}
    names = (
        dict(
            db.session.execute(
                select(Tenant.id, Tenant.name).where(Tenant.id.in_(ids))
            ).all()
        )
        if ids
        else {}
    )
    entries = []
    for r in rows:
        item = r.to_dict()
        item["club"] = names.get(r.tenant_id) if r.tenant_id else None
        entries.append(item)
    return jsonify(
        {
            "entries": entries,
            "total": total or 0,
            "page": page,
            "per_page": per_page,
            "retention_days": platform_monitor.RETENTION_DAYS,
        }
    ), 200


@platform_bp.get("/alerts/overview")
@require_global_permission(_DIAGNOSTICS)
def alerts_overview():
    """What is wrong right now, the latest alerts, and 24 h of warnings and
    errors per area, for manage › Platform › Alerts."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func, select

    from hubra.core.models.platform_event import PlatformEvent

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    rows = db.session.execute(
        select(PlatformEvent.category, PlatformEvent.level, func.count())
        .where(PlatformEvent.created_at >= since)
        .where(PlatformEvent.level.in_(("warning", "error")))
        .where(PlatformEvent.category != "alert")
        .group_by(PlatformEvent.category, PlatformEvent.level)
    ).all()
    counts: dict[str, dict[str, int]] = {}
    for category, level, n in rows:
        counts.setdefault(category, {"warning": 0, "error": 0})[level] = n
    recent = db.session.scalars(
        select(PlatformEvent)
        .where(PlatformEvent.category == "alert")
        .order_by(PlatformEvent.created_at.desc(), PlatformEvent.id.desc())
        .limit(10)
    ).all()
    from hubra.core.services import maintenance

    return jsonify(
        {
            "problems": platform_monitor.open_problems(),
            "recent": [r.to_dict() for r in recent],
            "counts": counts,
            "maintenance": maintenance.state(fresh=True),
            "switches": _alert_switches(),
        }
    ), 200


def _alert_switches() -> dict:
    """The platform-wide alert switches: all on/off, and per type mail and
    Discord.  ``discordReady``: the platform Discord log is set up."""
    from hubra.core.services import platform_discord, platform_settings

    def _off(key: str) -> set[str]:
        return {t.strip() for t in platform_settings.get(key).split(",") if t.strip()}

    mail_off, discord_off = _off("alerts.mail_off"), _off("alerts.discord_off")
    try:
        channel_id, token = platform_discord._settings()
        discord_ready = bool(channel_id and token) and (
            "alerts" in platform_discord.enabled_categories()
        )
    except Exception:  # noqa: BLE001
        discord_ready = False
    return {
        "enabled": platform_settings.get("alerts.enabled") != "off",
        "discordReady": discord_ready,
        "types": {
            t: {"mail": t not in mail_off, "discord": t not in discord_off}
            for t in platform_monitor.ALERT_TYPES
        },
    }


@platform_bp.get("/alerts/switches")
@require_global_permission(_DIAGNOSTICS)
def get_alert_switches():
    return jsonify(_alert_switches()), 200


@platform_bp.put("/alerts/switches")
@require_global_permission(_PERM)
def update_alert_switches():
    """Body ``{"enabled": bool, "types": {"<type>": {"mail": bool,
    "discord": bool}}}``; what is left out keeps its value."""
    from hubra.core.services import platform_settings

    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not body:
        return api_error("VALIDATION_ERROR", "Expected an object", 400)
    current = _alert_switches()
    values: dict = {}
    if "enabled" in body:
        if not isinstance(body["enabled"], bool):
            return api_error("VALIDATION_ERROR", "enabled is true or false", 400)
        values["alerts.enabled"] = None if body["enabled"] else "off"
    types = body.get("types", {})
    if not isinstance(types, dict):
        return api_error("VALIDATION_ERROR", "types is an object", 400)
    merged = {t: dict(v) for t, v in current["types"].items()}
    for t, chans in types.items():
        if t not in merged or not isinstance(chans, dict):
            return api_error("VALIDATION_ERROR", f"Unknown alert type: {t}", 400)
        for ch, on in chans.items():
            if ch not in ("mail", "discord") or not isinstance(on, bool):
                return api_error(
                    "VALIDATION_ERROR", f"{t}: mail and discord are true or false", 400
                )
            merged[t][ch] = on
    if types:
        for ch in ("mail", "discord"):
            off = [t for t, v in merged.items() if not v[ch]]
            values[f"alerts.{ch}_off"] = ",".join(off) or None
    platform_settings.set_many(values, actor_id=g.system_user.id)
    db.session.commit()
    return jsonify(_alert_switches()), 200


@platform_bp.get("/maintenance")
@require_global_permission(_DIAGNOSTICS)
def get_maintenance():
    from hubra.core.services import maintenance

    return jsonify(maintenance.state(fresh=True)), 200


@platform_bp.put("/maintenance")
@require_global_permission(_PERM)
def set_maintenance():
    """Body ``{"on": bool, "message": str, "minutes": int | null}``."""
    from hubra.core.services import maintenance

    body = request.get_json(silent=True) or {}
    if not isinstance(body.get("on"), bool):
        return api_error("VALIDATION_ERROR", "on is true or false", 400)
    if not body["on"]:
        return jsonify(maintenance.turn_off(actor_id=g.system_user.id)), 200
    minutes = body.get("minutes")
    if minutes is not None and (
        not isinstance(minutes, int)
        or isinstance(minutes, bool)
        or not 1 <= minutes <= 7 * 24 * 60
    ):
        return api_error("VALIDATION_ERROR", "minutes is 1 to 10080, or null", 400)
    message = body.get("message") or ""
    if not isinstance(message, str) or len(message) > 500:
        return api_error(
            "VALIDATION_ERROR", "message is text up to 500 characters", 400
        )
    return jsonify(
        maintenance.turn_on(message.strip(), minutes, actor_id=g.system_user.id)
    ), 200


def _parse_when(value, field: str):
    from datetime import datetime, timezone

    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} is an ISO time")
    try:
        at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{field} is an ISO time") from None
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def _club_names(windows) -> dict[int, str]:
    from sqlalchemy import select

    from hubra.core.models.tenant import Tenant

    ids = {i for w in windows for i in (w.tenant_ids or [])}
    if not ids:
        return {}
    return dict(
        db.session.execute(
            select(Tenant.id, Tenant.name).where(Tenant.id.in_(ids))
        ).all()
    )


@platform_bp.get("/maintenance/windows")
@require_global_permission(_DIAGNOSTICS)
def list_maintenance_windows():
    """Planned, running and the last 20 past windows (newest first)."""
    from datetime import datetime, timezone

    from sqlalchemy import or_, select

    from hubra.core.models.maintenance_window import MaintenanceWindow
    from hubra.core.services import maintenance

    now = datetime.now(timezone.utc)
    live = MaintenanceWindow.cancelled_at.is_(None) & (MaintenanceWindow.ends_at > now)
    current = db.session.scalars(
        select(MaintenanceWindow).where(live).order_by(MaintenanceWindow.starts_at)
    ).all()
    past = db.session.scalars(
        select(MaintenanceWindow)
        .where(
            or_(
                MaintenanceWindow.cancelled_at.isnot(None),
                MaintenanceWindow.ends_at <= now,
            )
        )
        .order_by(MaintenanceWindow.starts_at.desc())
        .limit(20)
    ).all()
    names = _club_names([*current, *past])
    return jsonify(
        {
            "current": [maintenance.window_json(w, names) for w in current],
            "past": [maintenance.window_json(w, names) for w in past],
            "notice_hours": list(maintenance.NOTICE_HOURS),
        }
    ), 200


@platform_bp.post("/maintenance/windows")
@require_global_permission(_PERM)
def create_maintenance_window():
    """Body ``{"starts_at", "ends_at", "message", "tenant_ids": [..] | null,
    "notice_hours"}``; ``tenant_ids`` null means every club."""
    from hubra.core.services import maintenance

    body = request.get_json(silent=True) or {}
    try:
        starts_at = _parse_when(body.get("starts_at"), "starts_at")
        ends_at = _parse_when(body.get("ends_at"), "ends_at")
    except ValueError as exc:
        return api_error("VALIDATION_ERROR", str(exc), 400)
    message = body.get("message") or ""
    tenant_ids = body.get("tenant_ids")
    notice = body.get("notice_hours", 24)
    if not isinstance(message, str):
        return api_error("VALIDATION_ERROR", "message is text", 400)
    if tenant_ids is not None and (
        not isinstance(tenant_ids, list)
        or not all(isinstance(i, int) and not isinstance(i, bool) for i in tenant_ids)
    ):
        return api_error(
            "VALIDATION_ERROR", "tenant_ids is a list of ids, or null", 400
        )
    if not isinstance(notice, int) or isinstance(notice, bool):
        return api_error("VALIDATION_ERROR", "notice_hours is a number", 400)
    try:
        window = maintenance.schedule(
            starts_at,
            ends_at,
            message.strip(),
            tenant_ids,
            notice,
            actor_id=g.system_user.id,
        )
    except maintenance.WindowError as exc:
        return api_error("VALIDATION_ERROR", str(exc), 400)
    _audit(
        "platform.maintenance.scheduled",
        "MaintenanceWindow",
        str(window.id),
        {
            "starts_at": window.starts_at.isoformat(),
            "ends_at": window.ends_at.isoformat(),
            "tenant_ids": window.tenant_ids,
            "notice_hours": window.notice_hours,
        },
    )
    db.session.commit()
    return jsonify(
        {"window": maintenance.window_json(window, _club_names([window]))}
    ), 201


@platform_bp.post("/maintenance/windows/<int:window_id>/cancel")
@require_global_permission(_PERM)
def cancel_maintenance_window(window_id: int):
    """Cancel a planned window, or end a running one now."""
    from hubra.core.services import maintenance

    try:
        window = maintenance.cancel(window_id, actor_id=g.system_user.id)
    except LookupError:
        return api_error("NOT_FOUND", "No such window", 404)
    except maintenance.WindowError as exc:
        return api_error("CONFLICT", str(exc), 409)
    _audit("platform.maintenance.cancelled", "MaintenanceWindow", str(window.id))
    db.session.commit()
    return jsonify(
        {"window": maintenance.window_json(window, _club_names([window]))}
    ), 200


@platform_bp.get("/alerts/performance")
@require_global_permission(_DIAGNOSTICS)
def alerts_performance():
    """API timing per route and slow queries, for manage › Platform › Alerts
    › Performance.  ``hours``: 1 to 24 clock hours, the current one included."""
    from hubra.core.services import perf_monitor

    try:
        hours = int(request.args.get("hours", 24))
    except ValueError:
        return api_error("VALIDATION_ERROR", "hours must be a number", 400)
    return jsonify(perf_monitor.summary(hours)), 200


@platform_bp.get("/alerts/me")
@require_global_permission(_DIAGNOSTICS)
def my_alerts():
    """Which alert mails the signed-in platform admin gets."""
    user = g.system_user
    return jsonify(
        {
            "alerts": platform_monitor.prefs_for(user),
            "email": user.email,
            # Support sees the alerts page but is not mailed.
            "receives": platform_monitor.gets_alert_mails(user),
            "cooldownMinutes": int(platform_monitor.cooldown().total_seconds() // 60),
        }
    ), 200


@platform_bp.put("/alerts/me")
@require_global_permission(_DIAGNOSTICS)
def update_my_alerts():
    """Body ``{"<type>": bool, ...}`` for the types in
    ``platform_monitor.ALERT_TYPES``; types left out keep their value."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not body:
        return api_error("VALIDATION_ERROR", "Expected an object of alert types", 400)
    unknown = [k for k in body if k not in platform_monitor.ALERT_TYPES]
    if unknown or not all(isinstance(v, bool) for v in body.values()):
        return api_error(
            "VALIDATION_ERROR",
            "Alert types are "
            + ", ".join(platform_monitor.ALERT_TYPES)
            + " and each is true or false",
            400,
        )
    user = g.system_user
    user.platform_alerts = {**platform_monitor.prefs_for(user), **body}
    db.session.commit()
    return jsonify({"alerts": platform_monitor.prefs_for(user)}), 200


# ── Translation suggestions from clubs ──────────────────────────────────────


@platform_bp.get("/translation-requests")
@require_global_permission(_PERM)
def list_translation_requests():
    """Clubs' suggestions; ``?status=pending|accepted|rejected`` (all if left out)."""
    from hubra.api.i18n import requests as suggestions

    status = request.args.get("status") or None
    if status and status not in suggestions.STATUSES:
        return api_error("VALIDATION_ERROR", "Unknown status", 400)
    return jsonify(suggestions.listing(status)), 200


@platform_bp.post("/translation-requests/<int:request_id>")
@require_global_permission(_PERM)
def decide_translation_request(request_id: int):
    """Body: ``{"accept": bool, "value"?: str, "note"?: str}``.

    Accepting writes the text (``value`` if the admin reworded it) for every
    club; rejecting keeps the text and tells the club why in ``note``.
    """
    from hubra.api.i18n import requests as suggestions
    from hubra.core.models.translation_request import TranslationRequest

    body = request.get_json(silent=True) or {}
    if not isinstance(body.get("accept"), bool):
        return api_error("VALIDATION_ERROR", "accept must be true or false", 400)
    value = body.get("value")
    note = body.get("note")
    if (value is not None and not isinstance(value, str)) or (
        note is not None and not isinstance(note, str)
    ):
        return api_error("VALIDATION_ERROR", "value and note must be text", 400)
    req = db.session.get(TranslationRequest, request_id)
    if req is None:
        return api_error("NOT_FOUND", "Translation request not found", 404)
    actor = getattr(g, "system_user", None)
    try:
        suggestions.decide(req, body["accept"], getattr(actor, "id", None), value, note)
    except suggestions.RequestError as exc:
        db.session.rollback()
        return api_error("CONFLICT", str(exc), 409)
    _audit(
        "accept_translation_request"
        if body["accept"]
        else "reject_translation_request",
        "TranslationRequest",
        str(req.id),
        {"locale": req.locale, "key": req.key, "tenant_id": req.tenant_id},
    )
    db.session.commit()
    return jsonify(req.to_dict()), 200


# ── Encryption keys ──────────────────────────────────────────────────────────


def _report(report) -> dict:
    return {
        "total": report.total,
        "current": report.current,
        "old_key": report.old_key,
        "unreadable": sum(report.unreadable.values()),
        "rotated": report.rotated,
        "new_keys": report.new_keys,
        "clean": report.clean,
    }


@platform_bp.get("/encryption")
@require_global_permission(_PERM)
def encryption_status():
    """The master key, each club's data key and backup key, and how many
    stored values are not on the current keys yet."""
    from flask import current_app
    from sqlalchemy import func, select

    from hubra.core.crypto import old_keys
    from hubra.core.models.data_key import DataKey
    from hubra.core.models.tenant import Tenant
    from hubra.core.services import secret_store

    newest = dict(
        db.session.execute(
            select(DataKey.scope, func.max(DataKey.version)).group_by(DataKey.scope)
        ).all()
    )
    created = {
        (k.scope, k.version): k.created_at
        for k in db.session.scalars(select(DataKey)).all()
    }
    clubs = []
    for t in db.session.scalars(
        select(Tenant).where(Tenant.deleted_at.is_(None)).order_by(Tenant.name)
    ).all():
        version = newest.get(f"c{t.id}")
        at = created.get((f"c{t.id}", version))
        clubs.append(
            {
                "tenant_id": t.id,
                "slug": t.slug,
                "name": t.name,
                "key_version": version,
                "key_created_at": at.isoformat() if at else None,
                "backup_public_key": t.backup_public_key,
            }
        )
    return jsonify(
        {
            "master": {
                "fernet_key_set": bool(current_app.config.get("FERNET_KEY")),
                "old_keys": len(old_keys()),
            },
            "values": _report(secret_store.check()),
            "clubs": clubs,
        }
    ), 200


@platform_bp.post("/encryption/rotate")
@require_global_permission(_PERM)
@require_step_up
def encryption_rotate():
    """Move every stored value onto the current keys (after a master key
    change).  Body ``{"new_keys": true, "tenant_id": <id>?}`` also makes new
    data keys: for one club, or every club and the platform."""
    from hubra.core.models.tenant import Tenant
    from hubra.core.services import secret_store

    body = request.get_json(silent=True) or {}
    scopes = None
    if body.get("new_keys"):
        tenant_id = body.get("tenant_id")
        if tenant_id is not None:
            if db.session.get(Tenant, tenant_id) is None:
                return api_error("NOT_FOUND", "Club not found", 404)
            scopes = {f"c{int(tenant_id)}"}
        else:
            scopes = secret_store.scopes_in_use()
    report = secret_store.rotate()
    if scopes:
        fresh = secret_store.new_keys(scopes)
        report.rotated += fresh.rotated
        report.new_keys = fresh.new_keys
    _audit(
        "platform.encryption.rotate",
        "data_key",
        ",".join(sorted(scopes)) if scopes else "all",
        {"rotated": report.rotated, "new_keys": report.new_keys},
    )
    db.session.commit()
    return jsonify(_report(report)), 200


@platform_bp.put("/clubs/<int:tenant_id>/backup-key")
@require_global_permission(_PERM)
@require_step_up
def set_club_backup_key(tenant_id: int):
    """Body ``{"public_key": "age1..." | null}``: the club's own backup key.
    Its next backups are encrypted to it as well as to the platform key."""
    from hubra.core.models.tenant import Tenant
    from hubra.core.services.backup_crypto import split_keys, valid_public_key

    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None:
        return api_error("NOT_FOUND", "Club not found", 404)
    raw = (request.get_json(silent=True) or {}).get("public_key")
    if raw in (None, ""):
        tenant.backup_public_key = None
    else:
        keys = split_keys(raw) if isinstance(raw, str) else []
        if not keys or not all(valid_public_key(k) for k in keys):
            return api_error("VALIDATION_ERROR", "Not an age public key (age1...)", 400)
        tenant.backup_public_key = " ".join(keys)
    _audit(
        "platform.backup_key.update",
        "tenant",
        str(tenant_id),
        {"public_key": tenant.backup_public_key},
    )
    db.session.commit()
    return jsonify(
        {"tenant_id": tenant_id, "backup_public_key": tenant.backup_public_key}
    ), 200
