"""Platform monitoring: the outbound mail relays, the platform event log and
alert mails to platform staff.

* Every mail ``email._send_via_smtp`` hands to a relay is written to the
  event log (``platform_events``, category ``mail``): sent, sent through the
  fallback relay, or failed, with the relay and the error.  Never the body.
* ``check_relay`` logs in to the main or the fallback relay (connect, EHLO,
  STARTTLS, AUTH) without sending anything.  The beat task
  ``mail_monitor_tasks.check_mail_relays`` runs it every few minutes and logs
  a ``relay`` event when a relay goes down or comes back.
* Alerts go by mail to platform admins (superadmins and everyone holding
  ``platform.settings``; not Support, which only looks), each of whom picks
  the types they get (``users.platform_alerts``).  Every type but the state
  changes is sent at most once per cooldown (platform setting
  ``alerts.cooldown_minutes``).  The log keeps ``alerts.retention_days``.  When the platform Discord log
  (``services/platform_discord.py``) is set up, mail alerts go there too.

An alert about the relays is sent through the relays, so when both are down
it cannot reach anyone by mail: it is still in the event log, and on Discord
when the platform log is set up.

Writing the log must never stop a mail or a request: every write is caught
and logged, and on Postgres it uses its own connection, so it is kept even
when the caller's transaction is rolled back.
"""

from __future__ import annotations

import json
import logging
import smtplib
import ssl
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from flask import current_app
from sqlalchemy import func, insert, select

from hubra.core.extensions import db
from hubra.core.models.platform_event import PlatformEvent

logger = logging.getLogger(__name__)

# Defaults of the platform settings alerts.retention_days / cooldown_minutes.
RETENTION_DAYS = 30
COOLDOWN_MINUTES = 60
CHECK_TIMEOUT = 10  # seconds per relay check
# A relay counts as down after this many failed checks in a row, so one
# slow answer does not wake anybody.
DOWN_AFTER = 2

# Who counts as a platform admin for alert mails.
ADMIN_PERMISSIONS = ("platform.settings", "*")

ALERT_TYPES = (
    "relay_down",
    "fallback_used",
    "delivery_failed",
    "service_down",
    "backup_failed",
    "plugin_updates",
    "system",
)
# Off unless the admin turns them on: news, not trouble.
_OFF_BY_DEFAULT = frozenset({"plugin_updates"})
RELAYS = ("relay", "fallback")

_CHECK_KEY = "mail:monitor:check:{}"
# Without Redis (tests, a broken Redis) the last checks live here, per process.
_local_checks: dict[str, dict] = {}


# ── Event log ─────────────────────────────────────────────────────────────────


@contextmanager
def _connection():
    """A connection for log writes: the session's on SQLite (tests share one
    in-memory database), a separate one in its own transaction elsewhere."""
    if db.engine.dialect.name == "sqlite":
        yield db.session
        return
    with db.engine.begin() as conn:
        yield conn


def _tenant_id() -> int | None:
    try:
        from hubra.core.tenant.context import current_tenant

        tenant = current_tenant()
    except Exception:
        return None
    return getattr(tenant, "id", None)


def record(
    category: str,
    kind: str,
    message: str,
    *,
    level: str = "info",
    details: dict | None = None,
    tenant_id: int | None = None,
) -> None:
    """Add one event to the log.  Never raises."""
    try:
        with _connection() as conn:
            conn.execute(
                insert(PlatformEvent).values(
                    created_at=datetime.now(timezone.utc),
                    category=category,
                    kind=kind,
                    level=level,
                    tenant_id=tenant_id,
                    message=message[:2000],
                    details=details or {},
                )
            )
    except Exception:
        logger.warning("platform_event_write_failed kind=%s", kind, exc_info=True)


def _recent(kind: str, since: datetime) -> bool:
    try:
        with _connection() as conn:
            return (
                conn.execute(
                    select(PlatformEvent.id)
                    .where(PlatformEvent.category == "alert")
                    .where(PlatformEvent.kind == kind)
                    .where(PlatformEvent.created_at >= since)
                    .limit(1)
                ).first()
                is not None
            )
    except Exception:
        return False


def stats(hours: int = 24) -> dict:
    """How many mails were sent, sent through the fallback and failed."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = db.session.execute(
        select(PlatformEvent.kind, func.count())
        .where(PlatformEvent.category == "mail")
        .where(PlatformEvent.created_at >= since)
        .group_by(PlatformEvent.kind)
    ).all()
    counts = dict(rows)
    return {
        "hours": hours,
        "sent": counts.get("mail.sent", 0),
        "fallback": counts.get("mail.fallback", 0),
        "failed": counts.get("mail.failed", 0),
    }


def retention_days() -> int:
    from hubra.core.services import platform_settings

    return max(
        1, platform_settings.int_setting("alerts.retention_days", RETENTION_DAYS)
    )


def cooldown() -> timedelta:
    from hubra.core.services import platform_settings

    minutes = platform_settings.int_setting("alerts.cooldown_minutes", COOLDOWN_MINUTES)
    return timedelta(minutes=max(0, minutes))


def prune(days: int | None = None) -> int:
    """Delete events older than *days* (default: the retention setting).
    Returns how many went."""
    days = days if days is not None else retention_days()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = db.session.execute(
        PlatformEvent.__table__.delete().where(PlatformEvent.created_at < cutoff)
    )
    db.session.commit()
    return result.rowcount or 0


# ── Mail sends ────────────────────────────────────────────────────────────────


def _is_recipient_problem(exc: Exception | None) -> bool:
    """A refused address says nothing about the relay."""
    return isinstance(exc, smtplib.SMTPRecipientsRefused)


def record_mail(
    *,
    to_email: str,
    subject: str,
    relay_host: str,
    error: Exception | None,
    primary_host: str | None = None,
    primary_error: Exception | None = None,
    fallback: bool = False,
    notify: bool = True,
    test: bool = False,
) -> None:
    """Log one mail and raise an alert when the relays are in trouble.

    *error* set: every route failed.  *fallback*: the fallback relay
    delivered it (after *primary_error*, or because the main relay was
    marked down).  ``notify=False`` for the alert mails themselves and test
    mails, which are logged but never raise another alert.
    """
    details = {"to": to_email, "subject": subject[:300], "relay": relay_host}
    if test:
        details["test"] = True
    tenant_id = _tenant_id()

    if error is not None:
        details["error"] = str(error)[:500]
        if primary_error is not None and primary_error is not error:
            details["primary"] = primary_host
            details["primary_error"] = str(primary_error)[:500]
        recipient = _is_recipient_problem(error)
        record(
            "mail",
            "mail.failed",
            f"Not delivered to {to_email}: {subject}",
            level="warning" if recipient else "error",
            details=details,
            tenant_id=tenant_id,
        )
        if notify and not recipient:
            alert(
                "delivery_failed",
                "Mail could not be delivered",
                [
                    f"A mail to {to_email} ({subject!r}) could not be sent.",
                    f"Error: {error}",
                    "Check the relays in manage › Diagnostics › Outbound mail.",
                ],
            )
        return

    if fallback:
        if primary_error is not None:
            details["primary"] = primary_host
            details["primary_error"] = str(primary_error)[:500]
        record(
            "mail",
            "mail.fallback",
            f"Sent to {to_email} through the fallback relay: {subject}",
            level="warning",
            details=details,
            tenant_id=tenant_id,
        )
        if (
            notify
            and primary_error is not None
            and not _is_recipient_problem(primary_error)
        ):
            alert(
                "fallback_used",
                "The main mail relay refused a mail; the fallback took over",
                [
                    f"Main relay {primary_host}: {primary_error}",
                    f"The fallback relay {relay_host} delivered it. Mail keeps "
                    "going through the fallback for 15 minutes before the "
                    "main relay is tried again.",
                ],
                level="warning",
            )
        return

    record(
        "mail",
        "mail.sent",
        f"Sent to {to_email}: {subject}",
        details=details,
        tenant_id=tenant_id,
    )


# ── Relay checks ──────────────────────────────────────────────────────────────


def _relay_config(which: str):
    from hubra.core.services import platform_settings

    if which == "fallback":
        return platform_settings.fallback_relay()
    r = platform_settings.relay()
    return r if r.host else None


def check_relay(which: str) -> dict:
    """Log in to the main relay or the fallback without sending a mail.

    Returns ``{"which", "configured", "ok", "host", "port", "latency_ms",
    "steps": [{"step", "ok", "ms", "error"?}], "error"?, "checked_at"}``.
    """
    cfg = _relay_config(which)
    now = time.time()
    if cfg is None:
        return {
            "which": which,
            "configured": False,
            "ok": None,
            "steps": [],
            "checked_at": now,
        }

    steps: list[dict] = []
    start = time.monotonic()

    def step(name: str, fn):
        t = time.monotonic()
        try:
            out = fn()
        except Exception as exc:
            steps.append(
                {
                    "step": name,
                    "ok": False,
                    "ms": int((time.monotonic() - t) * 1000),
                    "error": str(exc)[:300] or exc.__class__.__name__,
                }
            )
            raise
        steps.append(
            {"step": name, "ok": True, "ms": int((time.monotonic() - t) * 1000)}
        )
        return out

    context = ssl.create_default_context()
    if current_app.config.get("SMTP_TLS_VERIFY", True) is False:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    error = None
    server = None
    try:
        if cfg.port == 465:
            server = step(
                "connect",
                lambda: smtplib.SMTP_SSL(
                    cfg.host, cfg.port, timeout=CHECK_TIMEOUT, context=context
                ),
            )
        else:
            server = step(
                "connect",
                lambda: smtplib.SMTP(cfg.host, cfg.port, timeout=CHECK_TIMEOUT),
            )
        step("ehlo", server.ehlo)
        if cfg.port not in (25, 465):
            step("starttls", lambda: server.starttls(context=context))
            server.ehlo()
        if cfg.user and cfg.password:
            step("login", lambda: server.login(cfg.user, cfg.password))
    except Exception as exc:
        error = str(exc)[:300] or exc.__class__.__name__
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass

    result = {
        "which": which,
        "configured": True,
        "ok": error is None,
        "host": cfg.host,
        "port": cfg.port,
        "latency_ms": int((time.monotonic() - start) * 1000),
        "steps": steps,
        "checked_at": now,
    }
    if error:
        result["error"] = error
    return result


def _redis():
    from hubra.core.redis_client import get_redis_client

    return get_redis_client()


def last_check(which: str) -> dict | None:
    client = _redis()
    if client is not None:
        try:
            raw = client.get(_CHECK_KEY.format(which))
            return json.loads(raw) if raw else None
        except Exception:
            pass
    return _local_checks.get(which)


def _store_check(which: str, result: dict) -> None:
    _local_checks[which] = result
    client = _redis()
    if client is not None:
        try:
            client.set(_CHECK_KEY.format(which), json.dumps(result), ex=24 * 3600)
        except Exception:
            pass


def run_check(which: str, *, scheduled: bool = False) -> dict:
    """Check one relay, remember the result and log a change of state.

    The failure count carries over from the last check, so a relay counts
    as down (and the ``relay_down`` alert goes out) only after
    ``DOWN_AFTER`` failures in a row, and as back on its first good check.
    """
    previous = last_check(which) or {}
    result = check_relay(which)
    if not result["configured"]:
        _store_check(which, result)
        return result

    was_down = bool(previous.get("down"))
    failures = 0 if result["ok"] else int(previous.get("failures") or 0) + 1
    down = failures >= DOWN_AFTER or (was_down and not result["ok"])
    result["failures"] = failures
    result["down"] = down
    result["scheduled"] = scheduled
    _store_check(which, result)

    name = "Main relay" if which == "relay" else "Fallback relay"
    where = f"{result['host']}:{result['port']}"
    if down and not was_down:
        record(
            "relay",
            "relay.down",
            f"{name} {where} is down: {result.get('error')}",
            level="error",
            details={
                "relay": which,
                "host": result["host"],
                "error": result.get("error"),
                "steps": result["steps"],
            },
        )
        alert(
            "relay_down",
            f"{name} {where} is down",
            [
                f"{failures} checks in a row failed.",
                f"Error: {result.get('error')}",
                (
                    "Mail goes through the fallback relay while this lasts."
                    if which == "relay" and _relay_config("fallback")
                    else "Mail that needs this relay is not delivered."
                ),
            ],
            throttle=False,
        )
    elif was_down and not down:
        record(
            "relay",
            "relay.up",
            f"{name} {where} is working again",
            details={"relay": which, "host": result["host"]},
        )
        alert(
            "relay_down",
            f"{name} {where} is working again",
            [f"The check just logged in after {previous.get('failures')} failures."],
            level="info",
            throttle=False,
        )
    return result


def primary_down() -> dict:
    """Whether mail skips the main relay right now, and for how much longer."""
    from hubra.core.services.email import _PRIMARY_DOWN_KEY

    client = _redis()
    if client is None:
        return {"active": False, "seconds_left": 0}
    try:
        ttl = int(client.ttl(_PRIMARY_DOWN_KEY))
    except Exception:
        return {"active": False, "seconds_left": 0}
    return {"active": ttl > 0, "seconds_left": max(ttl, 0)}


def clear_primary_down() -> None:
    from hubra.core.services.email import _PRIMARY_DOWN_KEY

    client = _redis()
    if client is not None:
        try:
            client.delete(_PRIMARY_DOWN_KEY)
        except Exception:
            pass


# ── Alerts ────────────────────────────────────────────────────────────────────


def default_prefs() -> dict[str, bool]:
    return {t: t not in _OFF_BY_DEFAULT for t in ALERT_TYPES}


def prefs_for(user) -> dict[str, bool]:
    stored = user.platform_alerts or {}
    defaults = default_prefs()
    return {t: bool(stored.get(t, defaults[t])) for t in ALERT_TYPES}


def recipients(alert_type: str) -> list:
    """Platform admins who get *alert_type*: superadmins and holders of
    ``platform.settings``, active, who did not turn it off.  Support (only
    ``platform.diagnostics``) sees the alerts page but gets no mail."""
    from hubra.core.models.user import User

    users = db.session.scalars(
        select(User)
        .where(User.is_disabled.is_(False))
        .where((User.is_superadmin.is_(True)) | (User.id.in_(_admin_ids())))
        .order_by(User.id)
    ).all()
    return [u for u in users if prefs_for(u).get(alert_type, False)]


def gets_alert_mails(user) -> bool:
    """Whether *user* is a platform admin alert mails go to."""
    if user.is_superadmin:
        return True
    return user.id in set(db.session.scalars(_admin_ids()).all())


def _admin_ids():
    from hubra.core.models.global_role import (
        GlobalPermission,
        GlobalRolePermission,
        UserGlobalRole,
    )

    return select(UserGlobalRole.user_id).where(
        UserGlobalRole.role_id.in_(
            select(GlobalRolePermission.role_id)
            .join(
                GlobalPermission,
                GlobalPermission.id == GlobalRolePermission.permission_id,
            )
            .where(GlobalPermission.key.in_(ADMIN_PERMISSIONS))
        )
    )


def alert(
    alert_type: str,
    subject: str,
    lines: list[str],
    *,
    level: str = "error",
    throttle: bool = True,
) -> bool:
    """Log an alert and have it mailed to platform staff.  Never raises.

    With *throttle*, an alert type that went out within the cooldown
    is not sent again (the event that caused it is in the log anyway).
    Returns True when the alert was sent off.
    """
    try:
        now = datetime.now(timezone.utc)
        wait = cooldown() if throttle else timedelta(0)
        if wait and _recent(alert_type, now - wait):
            return False
        record(
            "alert",
            alert_type,
            subject,
            level=level,
            details={"lines": lines},
        )
        from hubra.core.tasks.mail_monitor_tasks import send_platform_alert

        try:
            send_platform_alert.apply_async(
                args=(alert_type, subject, lines, level), retry=False
            )
        except Exception:
            # No broker: send it here rather than not at all.
            logger.warning("platform_alert_queue_failed", exc_info=True)
            deliver_alert(alert_type, subject, lines, level)
        return True
    except Exception:
        logger.warning("platform_alert_failed type=%s", alert_type, exc_info=True)
        return False


def _manage_url() -> str:
    from hubra.core.services import platform_settings

    try:
        return platform_settings.get("alerts.manage_url").rstrip("/")
    except Exception:  # noqa: BLE001
        return str(current_app.config.get("MANAGE_BASE_URL") or "").rstrip("/")


def _instance_name() -> str:
    from urllib.parse import urlparse

    cfg = current_app.config
    for url in (_manage_url(), cfg.get("FRONTEND_BASE_URL"), cfg.get("API_PUBLIC_URL")):
        host = urlparse(str(url or "")).netloc
        if host:
            return host
    import socket

    return socket.gethostname()


def _alert_body(
    user, alert_type: str, subject: str, lines: list[str], level: str
) -> tuple[str, str, str]:
    """The alert in the Hubra mail layout, in the admin's language.  The
    subject and lines stay as written (English, like the SMTP errors and
    task names in them).  Returns ``(html, text, subject)``."""
    from zoneinfo import ZoneInfo

    from hubra.core.services.mail_i18n import _HUBRA_MARK, render_mail_template

    import base64

    cfg = current_app.config
    locale = "en-GB" if (user.language or "").lower().startswith("en") else "de-CH"
    try:
        zone = ZoneInfo(str(cfg.get("MAIL_TIMEZONE") or "Europe/Zurich"))
    except Exception:
        zone = ZoneInfo("Europe/Zurich")
    manage = _manage_url()
    level = level if level in ("error", "warning", "info") else "error"
    from hubra.core.services.mail_i18n import get_mail_translator

    t = get_mail_translator(locale)
    return render_mail_template(
        "platform_alert",
        locale=locale,
        name=user.first_name or user.name or user.email,
        club_name="Hubra",
        # Always the Hubra mark: an alert is the platform's, even when a
        # club's request raised it.
        logo_src="data:image/png;base64,"
        + base64.b64encode(_HUBRA_MARK.read_bytes()).decode(),
        alert_subject=subject,
        lines=lines,
        level=level,
        level_label=t(f"mail.email.platform_alert.level_{level}"),
        type_label=t(f"mail.email.platform_alert.type.{alert_type}"),
        when=datetime.now(zone).strftime("%d.%m.%Y, %H:%M"),
        instance=_instance_name(),
        alerts_url=f"{manage}/app/platform/alerts/overview" if manage else "",
    )


def _plain_alert(subject: str, lines: list[str]) -> tuple[str, str, str]:
    """When the template cannot be rendered (no translations, a broken
    database): the bare facts still go out."""
    from markupsafe import escape

    text = "\n".join([subject, "", *lines])
    html = f"<p><strong>{escape(subject)}</strong></p>" + "".join(
        f"<p>{escape(line)}</p>" for line in lines
    )
    return html, text, f"[Hubra] {subject}"


def deliver_alert(alert_type: str, subject: str, lines: list[str], level: str) -> int:
    """Mail the alert to every recipient (and post it to the platform Discord
    log when it is set up).  Returns how many mails went out."""
    from hubra.core.services import email, platform_settings
    from hubra.core.services.alerts import (
        COLOR_GREEN,
        COLOR_ORANGE,
        COLOR_RED,
        send_alert,
    )

    color = {"info": COLOR_GREEN, "warning": COLOR_ORANGE}.get(level, COLOR_RED)
    if alert_type != "system":  # system alerts came from send_alert already
        send_alert(f"Hubra: {subject}", "\n".join(lines), color=color, staff=False)

    relay = platform_settings.relay()
    if not relay.sender_email:
        logger.warning("platform_alert_no_sender type=%s", alert_type)
        return 0
    sent = 0
    for user in recipients(alert_type):
        try:
            html, text, mail_subject = _alert_body(
                user, alert_type, subject, lines, level
            )
        except Exception:
            logger.warning("platform_alert_template_failed", exc_info=True)
            html, text, mail_subject = _plain_alert(subject, lines)
        try:
            email._send_via_smtp(
                user.email,
                user.name or user.email,
                relay.sender_email,
                relay.sender_name,
                mail_subject,
                html,
                text,
                notify=False,
            )
            sent += 1
        except email.EmailDeliveryError:
            pass  # logged as mail.failed
    return sent


def system_alert(title: str, description: str, fields: list | None, color: int) -> None:
    """From ``services/alerts.py``: Redis, database, disk, failing tasks."""
    from hubra.core.services.alerts import COLOR_GREEN, COLOR_ORANGE

    level = (
        "info"
        if color == COLOR_GREEN
        else "warning"
        if color == COLOR_ORANGE
        else "error"
    )
    lines = [description] + [
        f"{f.get('name')}: {f.get('value')}" for f in (fields or [])
    ]
    record("system", "system.alert", title, level=level, details={"lines": lines})
    # Their own code already keeps them from repeating (state changes,
    # an hour per task), so no cooldown here: a recovery must not be eaten
    # by the alert before it.
    alert("system", title, lines, level=level, throttle=False)


# ── Other platform events ─────────────────────────────────────────────────────

# Health checks run every 20 s with a 1 s timeout: a service counts as down
# after this many failures in a row (about a minute), so a blip stays quiet.
SERVICE_DOWN_AFTER = 3
SERVICE_NAMES = {"db": "Database", "redis": "Redis", "imap": "IMAP"}


def watch_services(previous: dict | None, payload: dict) -> dict:
    """Compare a health run with the one before; log and alert outages.

    Keeps ``{"<service>": {"fails": n, "down_since": ts | None}}`` under
    ``payload["watch"]``, carried over from *previous* (the cached run).
    SMTP is left to the relay checks.  IMAP only counts with the mail module.

    The database cannot report its own outage by mail (the recipients, the
    relay and the log all live in it), so a database outage reaches Discord
    at once and everybody by mail when it is over, with how long it lasted.
    """
    from hubra.core.modules import is_enabled

    before = (previous or {}).get("watch") or {}
    watch: dict[str, dict] = {}
    now = time.time()
    for key, name in SERVICE_NAMES.items():
        svc = (payload.get("services") or {}).get(key)
        if svc is None or (key == "imap" and not is_enabled("mail")):
            continue
        state = dict(before.get(key) or {"fails": 0, "down_since": None})
        if svc.get("ok"):
            if state.get("down_since"):
                minutes = max(1, round((now - state["down_since"]) / 60))
                record(
                    "service",
                    "service.up",
                    f"{name} is reachable again after {minutes} min",
                    level="warning",
                    details={"service": key, "minutes": minutes},
                )
                alert(
                    "service_down",
                    f"{name} is reachable again",
                    [f"{name} was unreachable for about {minutes} minutes."],
                    level="warning",
                    throttle=False,
                )
            state = {"fails": 0, "down_since": None}
        else:
            state["fails"] = int(state.get("fails") or 0) + 1
            if state["fails"] == SERVICE_DOWN_AFTER and not state.get("down_since"):
                state["down_since"] = now
                error = svc.get("error") or "no answer"
                record(
                    "service",
                    "service.down",
                    f"{name} is unreachable: {error}",
                    level="error",
                    details={"service": key, "error": str(error)[:300]},
                )
                alert(
                    "service_down",
                    f"{name} is unreachable",
                    [
                        f"{SERVICE_DOWN_AFTER} health checks in a row failed.",
                        f"Error: {error}",
                    ],
                    throttle=False,
                )
        watch[key] = state
    payload["watch"] = watch
    return payload


def backups_failed(backup_type: str, records) -> None:
    """After a scheduled run: log and alert the scopes whose backup failed."""
    failed = [r for r in records if r.status != "completed"]
    if not failed:
        return
    names = [r.tenant_slug or "global" for r in failed]
    lines = [
        f"{r.tenant_slug or 'global'}: {(r.error_message or 'failed')[:300]}"
        for r in failed
    ]
    record(
        "backup",
        "backup.failed",
        f"Scheduled {backup_type} backup failed for {', '.join(names)}",
        level="error",
        details={"type": backup_type, "failed": names, "lines": lines},
    )
    alert(
        "backup_failed",
        f"{len(failed)} of {len(list(records))} scheduled backups failed",
        lines + ["See manage › Platform › Backups."],
    )


def plugin_news(result: dict) -> None:
    """After the plugin update check: log and announce what is new."""
    announced = result.get("announced") or []
    failed = result.get("failed") or []
    withdrawn = result.get("withdrawn") or []
    installed = result.get("installed") or []
    if not (announced or failed or withdrawn or installed):
        return
    lines = []
    if announced:
        lines.append("Update available: " + ", ".join(announced))
    if installed:
        lines.append("Updated automatically: " + ", ".join(installed))
    if failed:
        lines.append("Automatic update failed: " + ", ".join(failed))
    if withdrawn:
        lines.append("Withdrawn by its publisher: " + ", ".join(withdrawn))
    level = "warning" if failed or withdrawn else "info"
    record(
        "plugin",
        "plugin.updates",
        "; ".join(lines),
        level=level,
        details={
            "announced": announced,
            "installed": installed,
            "failed": failed,
            "withdrawn": withdrawn,
        },
    )
    alert(
        "plugin_updates",
        "Plugin updates",
        lines + ["See manage › Plugin catalogue."],
        level=level,
        throttle=False,
    )


# ── Open problems (the alerts overview) ───────────────────────────────────────


def open_problems() -> list[dict]:
    """What is wrong right now, worst first, for manage › Platform › Alerts.

    Each: ``{"id", "level", "area", "title", "detail", "since"?, "link"}``.
    """
    from hubra.api.health.cache import HealthCache

    problems: list[dict] = []

    def add(pid, level, area, title, detail="", since=None, link=""):
        problems.append(
            {
                "id": pid,
                "level": level,
                "area": area,
                "title": title,
                "detail": detail,
                "since": since,
                "link": link,
            }
        )

    # Background jobs: nothing below is checked while they stand still.
    cached = HealthCache.get()
    if cached is None or time.time() - float(cached.get("checked_at") or 0) > 60:
        add(
            "jobs",
            "error",
            "service",
            "Background jobs are not running",
            "Celery beat or the worker has not run the health check for over a "
            "minute: relay checks, backups, reminders and alert mails stand still.",
            link="/app/platform/diagnostics/health",
        )
    else:
        for key, state in (cached.get("watch") or {}).items():
            if state.get("down_since"):
                add(
                    f"service:{key}",
                    "error",
                    "service",
                    f"{SERVICE_NAMES.get(key, key)} is unreachable",
                    ((cached.get("services") or {}).get(key) or {}).get("error") or "",
                    since=state["down_since"],
                    link="/app/platform/diagnostics/health",
                )

    for which in RELAYS:
        check = last_check(which)
        if check and check.get("down"):
            add(
                f"relay:{which}",
                "error",
                "mail",
                ("Main relay" if which == "relay" else "Fallback relay") + " is down",
                check.get("error") or "",
                since=check.get("checked_at"),
                link="/app/platform/diagnostics/outbound-mail",
            )
    down = primary_down()
    if down["active"]:
        add(
            "relay:skipped",
            "warning",
            "mail",
            "Mail goes through the fallback relay",
            f"The main relay refused mail; it is tried again in "
            f"{max(1, down['seconds_left'] // 60)} min.",
            link="/app/platform/diagnostics/outbound-mail",
        )
    counts = stats(24)
    if counts["failed"]:
        add(
            "mail:failed",
            "warning",
            "mail",
            f"{counts['failed']} mails not delivered in 24 hours",
            "Refused addresses count too; the event log has each one.",
            link="/app/platform/alerts/events?category=mail&level=error",
        )

    problems.extend(_backup_problems())

    order = {"error": 0, "warning": 1, "info": 2}
    problems.sort(key=lambda p: order.get(p["level"], 3))
    return problems


def _backup_problems() -> list[dict]:
    """The newest scheduled backup of each scope failed, or none for 2 days."""
    from hubra.core.models.backup import BackupRecord
    from hubra.core.services import platform_settings

    if not platform_settings.get("backup.s3.bucket"):
        return []
    rows = db.session.scalars(
        select(BackupRecord)
        .where(BackupRecord.type.like("scheduled_%"))
        .where(
            BackupRecord.created_at >= datetime.now(timezone.utc) - timedelta(days=7)
        )
        .order_by(BackupRecord.created_at.desc())
    ).all()
    newest: dict[str, object] = {}
    for r in rows:
        newest.setdefault(r.tenant_slug or "global", r)
    out = []
    failed = [s for s, r in newest.items() if r.status == "failed"]
    if failed:
        out.append(
            {
                "id": "backup:failed",
                "level": "error",
                "area": "backup",
                "title": "Last scheduled backup failed for "
                + ", ".join(failed[:5])
                + ("…" if len(failed) > 5 else ""),
                "detail": (newest[failed[0]].error_message or "")[:300],
                "since": newest[failed[0]].created_at.timestamp(),
                "link": "/app/platform/backups",
            }
        )
    latest_ok = max(
        (r.created_at for r in rows if r.status == "completed"), default=None
    )
    if latest_ok is not None and latest_ok.tzinfo is None:
        latest_ok = latest_ok.replace(tzinfo=timezone.utc)
    if latest_ok is None or latest_ok < datetime.now(timezone.utc) - timedelta(days=2):
        out.append(
            {
                "id": "backup:none",
                "level": "warning",
                "area": "backup",
                "title": "No successful scheduled backup in 2 days",
                "detail": "Backups run daily at 03:00 UTC.",
                "since": None,
                "link": "/app/platform/backups",
            }
        )
    return out
