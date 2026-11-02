"""Platform admins in Discord: buttons on the platform log and admin commands.

Everything here happens on the platform's own Discord server, the one the
platform log channel (``discord.log_channel_id``) is on.  The Discord
plugin's interactions endpoint hands every click and command from that
server to ``handle`` before it looks for a club.

What it adds:

* **Club requests** get Approve / Reject buttons.  Approve sets the club up
  (in a background job, it can take longer than Discord waits); Reject asks
  for the reason, which goes to the requester.  When a request is decided,
  here or in manage, its message shows the outcome and loses its buttons.
* **Alerts** get Acknowledge, Silence 1 h and Open in manage.  Silencing
  stops that alert type (mail and Discord) for an hour.  When the problem
  behind an alert is gone, its message turns green ("resolved").
* **/plattform** ``status``, ``verein <name>``, ``backup [verein]`` and
  **/wartung** ``jetzt``, ``planen``, ``ende``, ``abbrechen``: commands on
  the platform server only (guild commands).
* The **daily digest** (08:00, platform time zone), **release
  announcements** and **security pings** (category ``digest``,
  ``releases``, ``security`` of the platform log).

Who may click or run what: the person must have linked their Discord
account to a Hubra account (SSO › Konto › Verknüpfungen), that account must
have two-factor sign-in on, and it needs the same platform permission as in
manage (``requests.approve``, ``platform.diagnostics``, ``platform.settings``,
``tenants.read``, ``backups.manage``).  Discord's own server permissions
only hide the commands from everybody else.
"""

from __future__ import annotations

import hashlib
import json
import re
import logging
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_log = logging.getLogger(__name__)

API = "https://discord.com/api/v10"
USER_AGENT = "Hubra (https://hubra.club, 1.0)"

EPHEMERAL = 1 << 6
MANAGE_GUILD = 1 << 5

# Interaction types and response types (Discord API).
PING, COMMAND, COMPONENT, AUTOCOMPLETE, MODAL = 1, 2, 3, 4, 5
R_MESSAGE, R_DEFERRED, R_DEFERRED_UPDATE, R_UPDATE, R_MODAL = 4, 5, 6, 7, 9

PREFIX = "p:"
COMMAND_NAMES = ("plattform", "wartung")

MUTE_SECONDS = 3600
# Alerts whose message is turned green when the problem is gone, by the
# ids (prefixes) of ``platform_monitor.open_problems`` that keep them open.
RESOLVES: dict[str, tuple[str, ...]] = {
    "relay_down": ("relay:relay", "relay:fallback"),
    "fallback_used": ("relay:skipped",),
    "service_down": ("service:", "jobs"),
    "backup_failed": ("backup:",),
    "delivery_failed": ("mail:failed",),
}
# An alert is only marked resolved after this long (checks need a moment).
RESOLVE_AFTER = timedelta(minutes=3)
# Tracked messages are forgotten after this long.
TRACK_DAYS = 7

COLOR_GOOD = 0x2ECC71
COLOR_BAD = 0xE74C3C
COLOR_INFO = 0x6D4AFF
COLOR_WARN = 0xF39C12

_ALERTS_KEY = "platform_bot:alerts"
_REQ_KEY = "platform_bot:req:"
_GUILD_KEY = "platform_bot:guild:"
_COMMANDS_KEY = "platform_bot:commands"

_local: dict[str, Any] = {}


# ── Small helpers ─────────────────────────────────────────────────────────────


def _redis():
    try:
        from hubra.core.redis_client import get_redis_client

        return get_redis_client()
    except Exception:  # noqa: BLE001
        return None


def _get(key: str) -> str | None:
    client = _redis()
    if client is not None:
        try:
            raw = client.get(key)
            return raw.decode() if isinstance(raw, bytes) else raw
        except Exception:  # noqa: BLE001
            pass
    value = _local.get(key)
    if value and value[1] and value[1] < time.time():
        _local.pop(key, None)
        return None
    return value[0] if value else None


def _set(key: str, value: str, ex: int | None = None, nx: bool = False) -> bool:
    client = _redis()
    if client is not None:
        try:
            return bool(client.set(key, value, ex=ex, nx=nx))
        except Exception:  # noqa: BLE001
            pass
    if nx and _get(key) is not None:
        return False
    _local[key] = (value, time.time() + ex if ex else None)
    return True


def _delete(key: str) -> None:
    client = _redis()
    if client is not None:
        try:
            client.delete(key)
        except Exception:  # noqa: BLE001
            pass
    _local.pop(key, None)


def _zone() -> ZoneInfo:
    from flask import current_app

    try:
        return ZoneInfo(current_app.config.get("MAIL_TIMEZONE") or "Europe/Zurich")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _local_time(at: datetime | None = None) -> str:
    at = at or datetime.now(timezone.utc)
    if at.tzinfo is None:  # stored as UTC without a zone (SQLite)
        at = at.replace(tzinfo=timezone.utc)
    at = at.astimezone(_zone())
    return f"{at:%d.%m.%Y %H:%M}"


def _manage_url(path: str = "") -> str:
    from hubra.core.services import platform_monitor

    base = platform_monitor._manage_url()
    return f"{base}{path}" if base else ""


def _token() -> str:
    from hubra.core.services import platform_settings

    return platform_settings.discord().bot_token


class BotError(RuntimeError):
    pass


def _bot(method: str, path: str, body: Any = None) -> Any:
    """One call to Discord's API as the Hubra bot.  Raises BotError."""
    token = _token()
    if not token:
        raise BotError("no bot token")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(  # noqa: S310
        f"{API}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raise BotError(f"Discord answered {exc.code} for {method} {path}") from None
    except Exception as exc:  # noqa: BLE001
        raise BotError(f"Discord unreachable: {exc}") from None
    return json.loads(raw) if raw else None


def _webhook(method: str, path: str, body: Any = None) -> Any:
    """Follow-ups to an interaction (no bot token: the interaction token
    in *path* is the credential)."""
    from hubra.core.services import platform_settings

    app_id = platform_settings.discord().client_id
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(  # noqa: S310
        f"{API}/webhooks/{app_id}/{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
        raw = resp.read()
    return json.loads(raw) if raw else None


def reply(text: str, embeds: list | None = None) -> dict:
    """An answer only the clicking person sees."""
    data: dict[str, Any] = {
        "content": text[:2000],
        "flags": EPHEMERAL,
        "allowed_mentions": {"parse": []},
    }
    if embeds:
        data["embeds"] = embeds
    return {"type": R_MESSAGE, "data": data}


def _button(label: str, custom_id: str, style: int) -> dict:
    return {"type": 2, "style": style, "label": label, "custom_id": custom_id}


def _link(label: str, url: str) -> dict:
    return {"type": 2, "style": 5, "label": label, "url": url}


# ── The platform server ───────────────────────────────────────────────────────


def guild_id() -> str:
    """The id of the server the platform log channel is on, or ""."""
    from hubra.core.services import platform_settings

    channel = platform_settings.get("discord.log_channel_id")
    if not channel or not _token():
        return ""
    key = _GUILD_KEY + channel
    cached = _get(key)
    if cached is not None:
        return cached
    try:
        guild = str((_bot("GET", f"/channels/{channel}") or {}).get("guild_id") or "")
    except BotError:
        _log.info("platform bot: cannot read the log channel", exc_info=True)
        return ""
    _set(key, guild, ex=3600)
    return guild


def is_platform_interaction(interaction: dict) -> bool:
    """A click or command meant for the platform, not for a club."""
    kind = interaction.get("type")
    data = interaction.get("data") or {}
    if kind in (COMPONENT, MODAL):
        ours = str(data.get("custom_id") or "").startswith(PREFIX)
    elif kind in (COMMAND, AUTOCOMPLETE):
        ours = data.get("name") in COMMAND_NAMES
    else:
        return False
    if not ours:
        return False
    guild = str(interaction.get("guild_id") or "")
    return bool(guild) and guild == guild_id()


# ── Who is clicking ───────────────────────────────────────────────────────────


class Refused(Exception):
    pass


def _discord_user(interaction: dict) -> dict:
    return (
        (interaction.get("member") or {}).get("user") or interaction.get("user") or {}
    )


def admin_for(interaction: dict, permission: str):
    """The Hubra account behind the click, if it may use *permission*.

    Raises ``Refused`` with the reason to show.
    """
    from sqlalchemy import select

    from hubra.api.auth import mfa
    from hubra.api.permissions import get_user_global_permissions
    from hubra.core.extensions import db
    from hubra.core.models.connected_app import ExternalAccount
    from hubra.core.models.user import User

    discord_id = str(_discord_user(interaction).get("id") or "")
    link = (
        db.session.scalar(
            select(ExternalAccount).where(
                ExternalAccount.provider == "discord",
                ExternalAccount.external_id == discord_id,
            )
        )
        if discord_id
        else None
    )
    user = db.session.get(User, link.user_id) if link else None
    if user is None or user.is_disabled:
        raise Refused(
            "Dein Discord-Konto ist mit keinem Hubra-Konto verknüpft. "
            "Verknüpfe es unter Konto › Verknüpfungen."
        )
    if not mfa.enabled(user):
        raise Refused(
            "Für Plattform-Aktionen in Discord braucht dein Hubra-Konto "
            "die Zwei-Faktor-Anmeldung."
        )
    perms = get_user_global_permissions(user.id)
    if "*" not in perms and permission not in perms:
        raise Refused(f"Dafür fehlt dir das Recht {permission}.")
    return user


# ── Alerts ────────────────────────────────────────────────────────────────────


def alert_buttons(alert_type: str) -> list:
    """Buttons under an alert: Acknowledge, Silence 1 h, Open in manage."""
    row = [
        _button("Bestätigen", f"p:al:ack:{alert_type}", 1),
        _button("1 h stumm", f"p:al:mute:{alert_type}", 2),
    ]
    url = _manage_url("/app/platform/alerts/overview")
    if url.startswith("https://"):
        row.append(_link("In manage öffnen", url))
    return [{"type": 1, "components": row}]


def track_alert(message: dict, alert_type: str) -> None:
    """Remember an alert's message, to mark it resolved later."""
    if not message or not message.get("id") or alert_type not in RESOLVES:
        return
    client = _redis()
    if client is None:
        return
    try:
        client.hset(
            _ALERTS_KEY,
            str(message["id"]),
            json.dumps(
                {
                    "type": alert_type,
                    "channel": str(message.get("channel_id") or ""),
                    "at": datetime.now(timezone.utc).isoformat(),
                }
            ),
        )
    except Exception:  # noqa: BLE001
        _log.debug("platform bot: alert not tracked", exc_info=True)


def muted_until(alert_type: str) -> str | None:
    """When the silence on *alert_type* ends (ISO), or None."""
    return _get(f"alerts:muted:{alert_type}")


def mute(alert_type: str, seconds: int = MUTE_SECONDS) -> str:
    until = (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(
        timespec="minutes"
    )
    _set(f"alerts:muted:{alert_type}", until, ex=seconds)
    return until


def _with_field(message: dict, name: str, value: str, color: int | None = None):
    embeds = [dict(e) for e in (message.get("embeds") or [])] or [{}]
    first = embeds[0]
    first["fields"] = [*(first.get("fields") or []), {"name": name, "value": value}][
        :25
    ]
    if color is not None:
        first["color"] = color
    return embeds


def _without(message: dict, *custom_ids: str) -> list:
    rows = []
    for row in message.get("components") or []:
        kept = [
            c
            for c in row.get("components") or []
            if not any(str(c.get("custom_id") or "").startswith(x) for x in custom_ids)
        ]
        if kept:
            rows.append({"type": 1, "components": kept})
    return rows


def _alert_click(interaction: dict, action: str, alert_type: str) -> dict:
    from hubra.core.services import platform_monitor

    message = interaction.get("message") or {}
    if action == "ack":
        user = admin_for(interaction, "platform.diagnostics")
        platform_monitor.record(
            "system",
            "alert.acknowledged",
            f"{user.name} acknowledged a {alert_type} alert in Discord",
            details={"type": alert_type, "userId": user.id},
        )
        return {
            "type": R_UPDATE,
            "data": {
                "embeds": _with_field(
                    message, "Bestätigt", f"{plain(user.name)}, {_local_time()}"
                ),
                "components": _without(message, "p:al:ack"),
            },
        }
    if action == "mute":
        user = admin_for(interaction, "platform.settings")
        until = mute(alert_type)
        platform_monitor.record(
            "system",
            "alert.muted",
            f"{user.name} silenced {alert_type} alerts for an hour in Discord",
            details={"type": alert_type, "until": until, "userId": user.id},
        )
        ends = _local_time(datetime.fromisoformat(until))
        return {
            "type": R_UPDATE,
            "data": {
                "embeds": _with_field(
                    message, "Stumm", f"{alert_type} bis {ends} ({plain(user.name)})"
                ),
                "components": _without(message, "p:al:mute"),
            },
        }
    return reply("Unbekannte Aktion.")


def resolve_alerts() -> int:
    """Turn alerts green whose problem is gone.  Returns how many."""
    client = _redis()
    if client is None:
        return 0
    try:
        tracked = client.hgetall(_ALERTS_KEY) or {}
    except Exception:  # noqa: BLE001
        return 0
    if not tracked:
        return 0
    from hubra.core.services import platform_monitor

    open_ids = [p["id"] for p in platform_monitor.open_problems()]
    now = datetime.now(timezone.utc)
    done = 0
    for raw_id, raw in tracked.items():
        msg_id = raw_id.decode() if isinstance(raw_id, bytes) else str(raw_id)
        try:
            info = json.loads(raw)
            at = datetime.fromisoformat(info["at"])
        except (ValueError, KeyError, TypeError):
            client.hdel(_ALERTS_KEY, msg_id)
            continue
        if now - at > timedelta(days=TRACK_DAYS):
            client.hdel(_ALERTS_KEY, msg_id)
            continue
        prefixes = RESOLVES.get(info.get("type"), ())
        if now - at < RESOLVE_AFTER or any(
            pid.startswith(prefixes) for pid in open_ids
        ):
            continue
        try:
            path = f"/channels/{info['channel']}/messages/{msg_id}"
            message = _bot("GET", path) or {}
            embeds = _with_field(message, "Behoben", _local_time(), COLOR_GOOD)
            title = embeds[0].get("title") or ""
            if title and not title.startswith("✅"):
                embeds[0]["title"] = f"✅ {title}"[:256]
            _bot(
                "PATCH",
                path,
                {
                    "embeds": embeds,
                    "components": _without(message, "p:al:ack", "p:al:mute"),
                },
            )
            done += 1
        except BotError:
            _log.info("platform bot: alert %s not updated", msg_id, exc_info=True)
        client.hdel(_ALERTS_KEY, msg_id)
    return done


# ── Club requests ─────────────────────────────────────────────────────────────


def request_buttons(entry) -> list | None:
    """Approve / Reject under a new club request's message."""
    if entry.action != "tenant_request.submit" or not entry.target_id:
        return None
    rid = entry.target_id
    row = [
        _button("Annehmen", f"p:req:ok:{rid}", 3),
        _button("Ablehnen", f"p:req:no:{rid}", 4),
    ]
    url = _manage_url("/app/platform/requests")
    if url.startswith("https://"):
        row.append(_link("In manage öffnen", url))
    return [{"type": 1, "components": row}]


def track_request(entry, message: dict) -> None:
    if not message or not message.get("id"):
        return
    _set(
        _REQ_KEY + str(entry.target_id),
        json.dumps(
            {"channel": str(message.get("channel_id") or ""), "id": message["id"]}
        ),
        ex=60 * 24 * 3600,
    )


def request_decided(entry) -> None:
    """Show the decision on the request's message, and drop its buttons."""
    if entry.action not in ("tenant_request.approve", "tenant_request.reject"):
        return
    key = _REQ_KEY + str(entry.target_id)
    raw = _get(key)
    if not raw:
        return
    from hubra.core.extensions import db
    from hubra.core.models.user import User

    actor = db.session.get(User, entry.actor_id) if entry.actor_id else None
    who = actor.name if actor else "jemand"
    approved = entry.action.endswith("approve")
    text = f"{'Angenommen' if approved else 'Abgelehnt'} von {who}, {_local_time()}"
    note = (entry.details or {}).get("note")
    if not approved and note:
        text += f"\nGrund: {str(note)[:900]}"
    try:
        info = json.loads(raw)
        path = f"/channels/{info['channel']}/messages/{info['id']}"
        message = _bot("GET", path) or {}
        _bot(
            "PATCH",
            path,
            {
                "embeds": _with_field(
                    message, "Entscheid", text, COLOR_GOOD if approved else COLOR_BAD
                ),
                "components": _without(message, "p:req:"),
            },
        )
    except (BotError, ValueError, KeyError):
        _log.info("platform bot: request message not updated", exc_info=True)
    _delete(key)


def _pending_request(raw_id: str):
    from hubra.core.extensions import db
    from hubra.core.models.tenant_request import TenantRequest

    req = db.session.get(TenantRequest, int(raw_id)) if raw_id.isdigit() else None
    if req is None:
        raise Refused("Diese Anfrage gibt es nicht mehr.")
    if req.status != "pending":
        raise Refused(f"Die Anfrage ist schon entschieden ({req.status}).")
    return req


def _request_click(interaction: dict, action: str, raw_id: str) -> dict:
    user = admin_for(interaction, "requests.approve")
    req = _pending_request(raw_id)
    if action == "ok":
        from hubra.core.tasks.platform_bot_tasks import approve_request

        approve_request.delay(req.id, user.id, interaction.get("token"))
        return {"type": R_DEFERRED, "data": {"flags": EPHEMERAL}}
    if action == "no":
        return {
            "type": R_MODAL,
            "data": {
                "custom_id": f"p:reqm:{req.id}",
                "title": f"Anfrage ablehnen: {req.name}"[:45],
                "components": [
                    {
                        "type": 1,
                        "components": [
                            {
                                "type": 4,
                                "custom_id": "note",
                                "label": "Grund (geht an die Person)",
                                "style": 2,
                                "required": False,
                                "max_length": 1000,
                            }
                        ],
                    }
                ],
            },
        }
    return reply("Unbekannte Aktion.")


def _modal_value(interaction: dict, field: str) -> str:
    for row in (interaction.get("data") or {}).get("components") or []:
        for comp in row.get("components") or []:
            if comp.get("custom_id") == field:
                return str(comp.get("value") or "")
    return ""


def _reject_submit(interaction: dict, raw_id: str) -> dict:
    from hubra.core.services import club_requests

    user = admin_for(interaction, "requests.approve")
    req = _pending_request(raw_id)
    try:
        req, notified = club_requests.reject(
            req.id, user.id, _modal_value(interaction, "note"), via="discord"
        )
    except club_requests.RequestDecisionError as exc:
        return reply(f"Nicht abgelehnt: {exc}")
    mail = "Die Person hat eine Mail bekommen." if notified else "Keine Mail versandt."
    return reply(f"Anfrage «{plain(req.name)}» abgelehnt. {mail}")


def approve_now(req_id: int, user_id: int) -> str:
    """Approve from Discord (the task).  Returns the text for the admin."""
    from hubra.core.services import club_requests

    try:
        req, tenant, notified = club_requests.approve(req_id, user_id, via="discord")
    except club_requests.RequestDecisionError as exc:
        return f"Nicht angenommen: {exc}"
    mail = "Die Person hat eine Mail bekommen." if notified else "Keine Mail versandt."
    return f"Verein «{plain(tenant.name)}» ({tenant.slug}) ist eingerichtet. {mail}"


def follow_up(interaction_token: str, text: str) -> None:
    """Replace the "thinking …" answer of a deferred interaction."""
    if not interaction_token:
        return
    try:
        _webhook(
            "PATCH",
            f"{interaction_token}/messages/@original",
            {"content": text[:2000], "allowed_mentions": {"parse": []}},
        )
    except Exception:  # noqa: BLE001
        _log.info("platform bot: follow-up not sent", exc_info=True)


# ── Commands ──────────────────────────────────────────────────────────────────

_EN = ("en-GB", "en-US")


def _loc(text: str) -> dict:
    return {lang: text for lang in _EN}


COMMANDS = [
    {
        "name": "plattform",
        "name_localizations": _loc("platform"),
        "description": "Hubra-Plattform (Plattform-Admins)",
        "description_localizations": _loc("Hubra platform (platform admins)"),
        "type": 1,
        "contexts": [0],
        "default_member_permissions": str(MANAGE_GUILD),
        "options": [
            {
                "type": 1,
                "name": "status",
                "description": "Version, Wartung, offene Probleme",
                "description_localizations": _loc(
                    "Version, maintenance, open problems"
                ),
            },
            {
                "type": 1,
                "name": "verein",
                "name_localizations": _loc("club"),
                "description": "Zustand eines Vereins",
                "description_localizations": _loc("Health of one club"),
                "options": [
                    {
                        "type": 3,
                        "name": "name",
                        "description": "Name oder Kürzel (slug)",
                        "description_localizations": _loc("Name or slug"),
                        "required": True,
                        "autocomplete": True,
                    }
                ],
            },
            {
                "type": 1,
                "name": "backup",
                "description": "Jetzt ein Backup machen",
                "description_localizations": _loc("Make a backup now"),
                "options": [
                    {
                        "type": 3,
                        "name": "verein",
                        "name_localizations": _loc("club"),
                        "description": "Nur dieser Verein (leer: Plattform)",
                        "description_localizations": _loc(
                            "Only this club (empty: platform)"
                        ),
                        "required": False,
                        "autocomplete": True,
                    }
                ],
            },
        ],
    },
    {
        "name": "wartung",
        "name_localizations": _loc("maintenance"),
        "description": "Wartungsmodus (Plattform-Admins)",
        "description_localizations": _loc("Maintenance mode (platform admins)"),
        "type": 1,
        "contexts": [0],
        "default_member_permissions": str(MANAGE_GUILD),
        "options": [
            {
                "type": 1,
                "name": "jetzt",
                "name_localizations": _loc("now"),
                "description": "Wartung jetzt beginnen",
                "description_localizations": _loc("Start maintenance now"),
                "options": [
                    {
                        "type": 4,
                        "name": "minuten",
                        "name_localizations": _loc("minutes"),
                        "description": "Erwartete Dauer",
                        "description_localizations": _loc("Expected length"),
                        "min_value": 1,
                        "max_value": 1440,
                    },
                    {
                        "type": 3,
                        "name": "text",
                        "description": "Hinweis für die Mitglieder",
                        "description_localizations": _loc("Notice for members"),
                        "max_length": 500,
                    },
                ],
            },
            {
                "type": 1,
                "name": "planen",
                "name_localizations": _loc("plan"),
                "description": "Wartung ankündigen",
                "description_localizations": _loc("Announce maintenance"),
                "options": [
                    {
                        "type": 3,
                        "name": "start",
                        "description": "Beginn, z. B. 22:00 oder 2026-11-05 22:00",
                        "description_localizations": _loc(
                            "Start, e.g. 22:00 or 2026-11-05 22:00"
                        ),
                        "required": True,
                    },
                    {
                        "type": 4,
                        "name": "minuten",
                        "name_localizations": _loc("minutes"),
                        "description": "Erwartete Dauer",
                        "description_localizations": _loc("Expected length"),
                        "required": True,
                        "min_value": 1,
                        "max_value": 1440,
                    },
                    {
                        "type": 3,
                        "name": "text",
                        "description": "Hinweis für die Mitglieder",
                        "description_localizations": _loc("Notice for members"),
                        "max_length": 500,
                    },
                ],
            },
            {
                "type": 1,
                "name": "ende",
                "name_localizations": _loc("end"),
                "description": "Wartung beenden",
                "description_localizations": _loc("End maintenance"),
            },
            {
                "type": 1,
                "name": "abbrechen",
                "name_localizations": _loc("cancel"),
                "description": "Geplante Wartung absagen",
                "description_localizations": _loc("Cancel planned maintenance"),
            },
        ],
    },
]


def register_commands(force: bool = False) -> bool:
    """Install /plattform and /wartung on the platform server (once per
    change).  True when Discord was called."""
    from hubra.core.services import platform_settings

    app_id = platform_settings.discord().client_id
    guild = guild_id()
    if not app_id or not guild:
        return False
    digest = hashlib.sha256(
        json.dumps([app_id, guild, COMMANDS], sort_keys=True).encode()
    ).hexdigest()
    if not force and _get(_COMMANDS_KEY) == digest:
        return False
    _bot("PUT", f"/applications/{app_id}/guilds/{guild}/commands", COMMANDS)
    _set(_COMMANDS_KEY, digest, ex=7 * 24 * 3600)
    return True


def _options(interaction: dict) -> tuple[str, dict, dict | None]:
    """(subcommand, {option: value}, focused option)."""
    subs = (interaction.get("data") or {}).get("options") or []
    if not subs:
        return "", {}, None
    sub = subs[0]
    values, focused = {}, None
    for opt in sub.get("options") or []:
        values[opt["name"]] = opt.get("value")
        if opt.get("focused"):
            focused = opt
    return sub.get("name") or "", values, focused


def _find_club(text: str):
    from sqlalchemy import func, or_, select

    from hubra.core.extensions import db
    from hubra.core.models.tenant import Tenant

    text = (text or "").strip()
    if not text:
        return None
    club = db.session.scalar(select(Tenant).where(Tenant.slug == text.lower()))
    if club is not None:
        return club
    return db.session.scalar(
        select(Tenant)
        .where(
            or_(
                func.lower(Tenant.name) == text.lower(),
                Tenant.name.ilike(f"%{text}%"),
            )
        )
        .order_by(Tenant.name)
        .limit(1)
    )


def _autocomplete(interaction: dict) -> dict:
    from sqlalchemy import or_, select

    from hubra.core.extensions import db
    from hubra.core.models.tenant import Tenant

    admin_for(interaction, "tenants.read")
    _, _, focused = _options(interaction)
    text = str((focused or {}).get("value") or "").strip()
    query = select(Tenant).order_by(Tenant.name).limit(25)
    if text:
        query = query.where(
            or_(Tenant.name.ilike(f"%{text}%"), Tenant.slug.ilike(f"%{text}%"))
        )
    choices = [
        {"name": f"{t.name} ({t.slug})"[:100], "value": t.slug}
        for t in db.session.scalars(query)
    ]
    return {"type": 8, "data": {"choices": choices}}


def _status(interaction: dict) -> dict:
    from sqlalchemy import func, select

    from hubra.api.version.services import VersionService
    from hubra.core.extensions import db
    from hubra.core.models.tenant import Tenant
    from hubra.core.services import maintenance, platform_monitor

    admin_for(interaction, "platform.diagnostics")
    problems = platform_monitor.open_problems()
    clubs = db.session.scalar(
        select(func.count()).select_from(Tenant).where(Tenant.status == "active")
    )
    state = maintenance.state(fresh=True)
    if state["active"]:
        wartung = "Ein" + (
            f" bis {_local_time(datetime.fromisoformat(state['until']))}"
            if state.get("until")
            else ""
        )
    else:
        upcoming = _next_window()
        wartung = f"Geplant ab {_local_time(upcoming.starts_at)}" if upcoming else "Aus"
    icons = {"error": "🔴", "warning": "🟠", "info": "🔵"}
    lines = [f"{icons.get(p['level'], '•')} {p['title']}" for p in problems[:15]]
    muted = [
        t for t in sorted(set(RESOLVES) | {"system", "upgrades"}) if muted_until(t)
    ]
    fields = [
        {"name": "Version", "value": VersionService.get_version(), "inline": True},
        {"name": "Aktive Vereine", "value": str(clubs or 0), "inline": True},
        {"name": "Wartung", "value": wartung, "inline": True},
        {
            "name": f"Offene Probleme ({len(problems)})",
            "value": "\n".join(lines)[:1000] or "Keine 🎉",
        },
    ]
    if muted:
        fields.append({"name": "Stumm", "value": ", ".join(muted)})
    embed = {
        "title": "Hubra-Plattform",
        "color": COLOR_BAD
        if any(p["level"] == "error" for p in problems)
        else COLOR_WARN
        if problems
        else COLOR_GOOD,
        "fields": fields,
    }
    return reply("", [embed])


def _club(interaction: dict, values: dict) -> dict:
    from hubra.core.services import tenant_health

    admin_for(interaction, "tenants.read")
    club = _find_club(str(values.get("name") or ""))
    if club is None:
        return reply("Kein Verein gefunden.")
    h = tenant_health.for_tenants([club]).get(club.id) or {}
    mail = h.get("mail") or {}
    alerts = h.get("alerts") or {}
    size = (h.get("storage_bytes") or 0) / (1024 * 1024)
    last = h.get("last_activity")
    fields = [
        {"name": "Status", "value": club.status, "inline": True},
        {"name": "Plan", "value": club.plan or "–", "inline": True},
        {
            "name": "Mitglieder",
            "value": f"{h.get('members', 0)} ({h.get('active_members', 0)} aktiv)",
            "inline": True,
        },
        {
            "name": "Letzte Aktivität",
            "value": _local_time(datetime.fromisoformat(last)) if last else "–",
            "inline": True,
        },
        {"name": "Speicher", "value": f"{size:.1f} MB", "inline": True},
        {
            "name": "Mails (24 h)",
            "value": f"{mail.get('sent', 0)} versandt, {mail.get('failed', 0)} fehlgeschlagen",
            "inline": True,
        },
        {"name": "Plugins", "value": str(h.get("plugins", 0)), "inline": True},
        {
            "name": "Warnungen",
            "value": f"{alerts.get('error', 0)} Fehler, {alerts.get('warning', 0)} Warnungen",
            "inline": True,
        },
        {
            "name": "Seit",
            "value": _local_time(club.created_at) if club.created_at else "–",
            "inline": True,
        },
    ]
    level = h.get("level")
    embed: dict[str, Any] = {
        "title": f"{club.name} ({club.slug})"[:256],
        "color": {"error": COLOR_BAD, "warning": COLOR_WARN}.get(level, COLOR_GOOD),
        "fields": fields,
    }
    url = _manage_url(f"/app/tenants/{club.id}")
    if url.startswith("https://"):
        embed["url"] = url
    return reply("", [embed])


def _backup(interaction: dict, values: dict) -> dict:
    from hubra.core.extensions import db
    from hubra.core.models.tenant import GlobalAuditEntry
    from hubra.core.tasks.backup_tasks import create_backup_task

    user = admin_for(interaction, "backups.manage")
    tenant_id = None
    label = "Plattform"
    if values.get("verein"):
        club = _find_club(str(values["verein"]))
        if club is None:
            return reply("Kein Verein gefunden.")
        tenant_id, label = club.id, f"{plain(club.name)} ({club.slug})"
    task = create_backup_task.delay(
        backup_type="manual", triggered_by=user.email, tenant_id=tenant_id
    )
    db.session.add(
        GlobalAuditEntry(
            tenant_id=None,
            actor_id=user.id,
            action="backup.create",
            target_type="backup",
            target_id=None,
            details={
                "task_id": getattr(task, "id", None),
                "via": "discord",
                **({"tenant_id": tenant_id} if tenant_id else {}),
            },
        )
    )
    db.session.commit()
    return reply(f"Backup gestartet: {label}. Das Ergebnis kommt in den Log.")


def _parse_start(text: str) -> datetime | None:
    """``22:00`` (today, or tomorrow when past), ``2026-11-05 22:00`` or
    ``05.11.2026 22:00``, in the platform time zone."""
    text = (text or "").strip()
    zone = _zone()
    now = datetime.now(zone)
    for fmt in ("%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M", "%d.%m. %H:%M"):
        try:
            at = datetime.strptime(text, fmt)
        except ValueError:
            continue
        if fmt == "%d.%m. %H:%M":
            at = at.replace(year=now.year)
        return at.replace(tzinfo=zone)
    try:
        hm = datetime.strptime(text, "%H:%M")
    except ValueError:
        return None
    at = now.replace(hour=hm.hour, minute=hm.minute, second=0, microsecond=0)
    return at + timedelta(days=1) if at <= now else at


def _next_window():
    """The next planned window for every club that has not started."""
    from hubra.core.services import maintenance

    now = datetime.now(timezone.utc)
    for w in maintenance._open_windows():
        starts = (
            w.starts_at
            if w.starts_at.tzinfo
            else w.starts_at.replace(tzinfo=timezone.utc)
        )
        if w.tenant_ids is None and starts > now:
            return w
    return None


def _maintenance(interaction: dict, sub: str, values: dict) -> dict:
    from hubra.core.services import maintenance

    user = admin_for(interaction, "platform.settings")
    if sub == "jetzt":
        minutes = values.get("minuten")
        state = maintenance.turn_on(
            str(values.get("text") or ""), int(minutes) if minutes else None, user.id
        )
        until = (
            f" bis {_local_time(datetime.fromisoformat(state['until']))}"
            if state.get("until")
            else ""
        )
        return reply(f"Wartung ist an{until}. Die Vereins-Apps zeigen den Hinweis.")
    if sub == "planen":
        start = _parse_start(str(values.get("start") or ""))
        if start is None:
            return reply(
                "Beginn nicht verstanden. Beispiel: 22:00 oder 2026-11-05 22:00."
            )
        if start <= datetime.now(timezone.utc):
            return reply("Der Beginn liegt in der Vergangenheit.")
        minutes = int(values.get("minuten") or 15)
        start = start.astimezone(timezone.utc)  # stored without its zone in SQLite
        try:
            maintenance.schedule(
                start,
                start + timedelta(minutes=minutes),
                str(values.get("text") or ""),
                None,
                notice_hours=24,
                actor_id=user.id,
            )
        except maintenance.WindowError as exc:
            return reply(f"Nicht geplant: {exc.args[0] if exc.args else exc}")
        return reply(
            f"Wartung für alle Vereine geplant ab {_local_time(start)}, "
            f"{minutes} Minuten. Die Vereins-Apps zeigen ab 24 Stunden vorher "
            "einen Hinweis; sie beginnt von selbst."
        )
    if sub == "ende":
        was = maintenance.state(fresh=True)
        maintenance.turn_off(user.id)
        return reply("Wartung beendet." if was["active"] else "Es lief keine Wartung.")
    if sub == "abbrechen":
        window = _next_window()
        if window is None:
            return reply("Es ist keine Wartung für alle Vereine geplant.")
        maintenance.cancel(window.id, user.id)
        return reply(f"Geplante Wartung ab {_local_time(window.starts_at)} abgesagt.")
    return reply("Unbekannter Befehl.")


def handle(interaction: dict) -> dict:
    """Answer one platform click or command (see ``is_platform_interaction``)."""
    kind = interaction.get("type")
    data = interaction.get("data") or {}
    try:
        if kind == AUTOCOMPLETE:
            return _autocomplete(interaction)
        if kind == COMMAND:
            sub, values, _ = _options(interaction)
            if data.get("name") == "wartung":
                return _maintenance(interaction, sub, values)
            if sub == "status":
                return _status(interaction)
            if sub == "verein":
                return _club(interaction, values)
            if sub == "backup":
                return _backup(interaction, values)
            return reply("Unbekannter Befehl.")
        parts = str(data.get("custom_id") or "").split(":")
        if kind == MODAL and len(parts) == 3 and parts[1] == "reqm":
            return _reject_submit(interaction, parts[2])
        if kind == COMPONENT and len(parts) == 4 and parts[1] == "req":
            return _request_click(interaction, parts[2], parts[3])
        if kind == COMPONENT and len(parts) == 4 and parts[1] == "al":
            from hubra.core.services.platform_monitor import ALERT_TYPES

            # Only known types: the type names a Redis key (mute).
            if parts[3] not in ALERT_TYPES:
                return reply("Unbekannte Aktion.")
            return _alert_click(interaction, parts[2], parts[3])
        return reply("Unbekannte Aktion.")
    except Refused as exc:
        if kind == AUTOCOMPLETE:
            return {"type": 8, "data": {"choices": []}}
        return reply(str(exc))
    except Exception:
        _log.exception("platform bot: interaction failed")
        from hubra.core.extensions import db

        db.session.rollback()
        return reply("Das hat nicht geklappt; der Fehler ist im Log.")


# ── Club servers ──────────────────────────────────────────────────────────────


def notify_clubs(kind: str, payload: dict) -> None:
    """Tell the clubs' Discord servers that opted in (``hubra_news`` for
    releases, ``maintenance_notices`` for maintenance), in the background."""
    try:
        from hubra.core.tasks.platform_bot_tasks import club_notice

        club_notice.delay(kind, payload)
    except Exception:  # noqa: BLE001
        _log.warning("platform bot: club notice %s not queued", kind, exc_info=True)


_RUNNING_KEY = "platform_bot:windows:running"


def window_notices(now: datetime | None = None) -> int:
    """Tell club servers when a planned window starts and when it is over.
    Returns how many notices were queued."""
    from hubra.core.services import maintenance

    now = now or datetime.now(timezone.utc)
    try:
        known = set(json.loads(_get(_RUNNING_KEY) or "[]"))
    except ValueError:
        known = set()
    running: dict[str, dict] = {}
    for w in maintenance._open_windows():
        notice = maintenance.window_notice(w)
        if datetime.fromisoformat(notice["start"]) <= now:
            running[str(w.id)] = notice
    sent = 0
    for wid, notice in running.items():
        if wid not in known:
            notify_clubs("maintenance_started", notice)
            sent += 1
    for wid in known - set(running):
        notify_clubs("maintenance_ended", {})
        sent += 1
    _set(_RUNNING_KEY, json.dumps(sorted(running)), ex=8 * 24 * 3600)
    return sent


def send_club_notices(kind: str, payload: dict) -> int:
    """Hand *kind* to every connected club server's ``platform_notice`` hook.
    Returns how many servers got it."""
    from sqlalchemy import select

    from hubra.core import apps
    from hubra.core.extensions import db
    from hubra.core.models.connected_app import ConnectedApp
    from hubra.core.models.tenant import Tenant
    from hubra.core.modules import is_enabled
    from hubra.core.tenant.context import in_club

    found = apps.provider("discord")
    if found is None:
        return 0
    notice = apps.hook(found[1], "platform_notice")
    if notice is None:
        return 0
    sent = 0
    conns = db.session.scalars(
        select(ConnectedApp).where(
            ConnectedApp.provider == "discord", ConnectedApp.status == "active"
        )
    ).all()
    only = payload.get("tenant_ids")  # a window for some clubs only
    for conn in conns:
        if only is not None and conn.tenant_id not in only:
            continue
        tenant = db.session.get(Tenant, conn.tenant_id)
        if tenant is None or tenant.status != "active":
            continue
        try:
            with in_club(tenant):
                if is_enabled("discord") and notice(conn, kind, payload):
                    sent += 1
        except Exception:  # noqa: BLE001
            _log.info("platform notice to club %s failed", tenant.id, exc_info=True)
    return sent


# ── Daily digest ──────────────────────────────────────────────────────────────


def digest_embed(now: datetime | None = None) -> dict:
    """The day's overview for the platform log."""
    from sqlalchemy import func, select

    from hubra.core.extensions import db
    from hubra.core.models.tenant import Tenant
    from hubra.core.models.tenant_request import TenantRequest
    from hubra.core.models.user import User
    from hubra.core.services import platform_monitor

    now = now or datetime.now(timezone.utc)
    since = now - timedelta(hours=24)
    clubs = db.session.scalars(
        select(Tenant).where(Tenant.created_at >= since).order_by(Tenant.name)
    ).all()
    signups = db.session.scalar(
        select(func.count()).select_from(User).where(User.created_at >= since)
    )
    pending = db.session.scalar(
        select(func.count())
        .select_from(TenantRequest)
        .where(TenantRequest.status == "pending")
    )
    mail = platform_monitor.stats(24)
    problems = platform_monitor.open_problems()
    slow = [p for p in problems if str(p.get("id", "")).startswith("perf")]
    other = [p for p in problems if p not in slow]
    plugin_updates = _plugin_updates()

    def names(rows):
        text = ", ".join(f"{plain(t.name)} ({t.slug})" for t in rows[:10])
        return text + (f" und {len(rows) - 10} weitere" if len(rows) > 10 else "")

    fields = [
        {
            "name": f"Neue Vereine ({len(clubs)})",
            "value": names(clubs) or "–",
        },
        {"name": "Neue Konten", "value": str(signups or 0), "inline": True},
        {"name": "Offene Anfragen", "value": str(pending or 0), "inline": True},
        {
            "name": "Mails",
            "value": f"{mail['sent']} versandt, {mail['fallback']} über Ersatz, "
            f"{mail['failed']} fehlgeschlagen",
            "inline": True,
        },
        {
            "name": f"Offene Probleme ({len(other)})",
            "value": "\n".join(f"• {p['title']}" for p in other[:8])[:1000] or "Keine",
        },
        {
            "name": "Langsame Endpunkte",
            "value": "\n".join(f"• {p['title']}" for p in slow[:5])[:1000] or "Keine",
        },
        {"name": "Plugin-Updates", "value": plugin_updates or "Keine"},
    ]
    embed: dict[str, Any] = {
        "title": f"Tagesübersicht {now.astimezone(_zone()):%d.%m.%Y}",
        "color": COLOR_WARN if other else COLOR_INFO,
        "fields": fields,
        "footer": {"text": "Hubra platform · digest"},
        "timestamp": now.isoformat(),
    }
    url = _manage_url("/app/platform/alerts/overview")
    if url.startswith("https://"):
        embed["url"] = url
    return embed


def _plugin_updates() -> str:
    """The newest "updates available" note of the plugin check, if any."""
    from sqlalchemy import select

    from hubra.core.extensions import db
    from hubra.core.models.platform_event import PlatformEvent

    event = db.session.scalar(
        select(PlatformEvent)
        .where(PlatformEvent.kind == "plugin.updates")
        .order_by(PlatformEvent.created_at.desc())
        .limit(1)
    )
    if event is None:
        return ""
    at = event.created_at
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - at > timedelta(days=2):
        return ""
    return (event.message or "")[:1000]


def send_digest(now: datetime | None = None) -> bool:
    from hubra.core.services import platform_discord

    if "digest" not in platform_discord.enabled_categories():
        return False
    platform_discord.post(digest_embed(now))
    return True


# ── Releases ──────────────────────────────────────────────────────────────────


def _announced(version: str) -> bool:
    from sqlalchemy import select

    from hubra.core.extensions import db
    from hubra.core.models.platform_event import PlatformEvent

    return (
        db.session.scalar(
            select(PlatformEvent.id)
            .where(PlatformEvent.kind == "release.announced")
            .where(PlatformEvent.message == version)
            .limit(1)
        )
        is not None
    )


def release_notes(version: str) -> dict | None:
    from hubra.api.version.services import VersionService

    for entry in VersionService.get_changelog("de"):
        if str(entry.get("version")) == version:
            return entry
    return None


def release_embed(version: str, entry: dict | None) -> dict:
    """``entry``: one changelog entry (``sections``: {heading: [items]})."""
    fields = []
    for heading, items in ((entry or {}).get("sections") or {}).items():
        text = "\n".join(f"• {item}" for item in items[:8])
        if len(items) > 8:
            text += f"\n… und {len(items) - 8} weitere"
        if text:
            fields.append({"name": str(heading)[:250] or "–", "value": text[:1000]})
    embed: dict[str, Any] = {
        "title": f"Hubra {version} läuft",
        "color": COLOR_INFO,
        "fields": fields[:10],
        "footer": {"text": "Hubra platform · releases"},
    }
    if entry and entry.get("date"):
        embed["description"] = f"Veröffentlicht am {entry['date']}"
    return embed


def announce_release() -> bool:
    """Post the running version's release notes once per version."""
    from hubra.api.version.services import VersionService
    from hubra.core.services import platform_discord, platform_monitor

    version = VersionService.get_version()
    if not version or _announced(version):
        return False
    if not _set(f"platform_bot:release:{version}", "1", ex=3600, nx=True):
        return False
    entry = release_notes(version)
    if "releases" in platform_discord.enabled_categories():
        try:
            platform_discord.post(release_embed(version, entry))
        except platform_discord.DiscordPostError:
            _delete(f"platform_bot:release:{version}")
            raise
    platform_monitor.record("system", "release.announced", version)
    notify_clubs(
        "release",
        {
            "version": version,
            "date": (entry or {}).get("date"),
            "sections": (entry or {}).get("sections") or {},
        },
    )
    return True


# ── Security pings ────────────────────────────────────────────────────────────

FAILED_LOGIN_THRESHOLD = 20
FAILED_LOGIN_WINDOW = 600
KEY_MAX_AGE_DAYS = 365


_MARKDOWN = re.compile(r"([\\`*_~|>\[\]()#<@])")


def plain(value, limit: int = 100) -> str:
    """Text a user typed (a name, the email tried at sign-in, a browser
    string) as one inert line: no Discord markdown, links or mentions."""
    text = " ".join(str(value or "").split())[:limit]
    return _MARKDOWN.sub(r"\\\1", text) or "–"


def security(title: str, lines: list[str], level: str = "warning") -> None:
    """Queue a security ping (after the commit)."""
    try:
        from hubra.core.tasks.after_commit import delay_after_commit
        from hubra.core.tasks.platform_bot_tasks import post_security

        delay_after_commit(post_security, title, lines, level)
    except Exception:  # noqa: BLE001
        _log.warning("platform bot: security ping not queued", exc_info=True)


def post_security_now(title: str, lines: list[str], level: str = "warning") -> bool:
    from hubra.core.services import platform_discord

    channel_id, token = platform_discord._settings()
    if not channel_id or not token:
        return False
    if "security" not in platform_discord.enabled_categories():
        return False
    platform_discord.post(
        {
            "title": f"🔐 {title}"[:256],
            "description": "\n".join(lines)[:3500],
            "color": COLOR_BAD if level == "error" else COLOR_WARN,
            "footer": {"text": "Hubra platform · security"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        channel_id=channel_id,
        token=token,
    )
    return True


def staff_new_device(user, ip: str, browser: str, platform: str) -> None:
    from hubra.api.auth import mfa

    try:
        if not mfa.is_staff(user):
            return
    except Exception:  # noqa: BLE001
        return
    security(
        "Plattform-Admin auf neuem Gerät",
        [
            f"**{plain(user.name)}** ({plain(user.email)}) "
            "hat sich auf einem neuen Gerät angemeldet.",
            f"Browser: {plain(browser)} · System: {plain(platform)}",
            f"IP: {plain(ip, 64)} · {_local_time()}",
        ],
    )


def staff_mfa_off(user) -> None:
    """Called when an account loses its last second step."""
    from hubra.api.auth import mfa

    try:
        if mfa.enabled(user) or not mfa.is_staff(user):
            return
    except Exception:  # noqa: BLE001
        return
    security(
        "Zwei-Faktor bei Plattform-Admin ausgeschaltet",
        [
            f"**{plain(user.name)}** ({plain(user.email)}) "
            "hat keine Zwei-Faktor-Anmeldung mehr.",
            "Seine Plattform-Rechte ruhen, bis sie wieder an ist "
            "(wenn MFA_REQUIRED_FOR_STAFF gilt).",
        ],
        level="error",
    )


def failed_login(ip: str | None, email: str = "") -> None:
    """Count a failed sign-in per address; ping once at the threshold."""
    if not ip:
        return
    client = _redis()
    if client is None:
        return
    key = f"sec:fail:{ip}"
    try:
        count = client.incr(key)
        if count == 1:
            client.expire(key, FAILED_LOGIN_WINDOW)
    except Exception:  # noqa: BLE001
        return
    if count == FAILED_LOGIN_THRESHOLD:
        try:
            from hubra.core.tasks.platform_bot_tasks import post_security

            post_security.delay(
                "Viele fehlgeschlagene Anmeldungen",
                [
                    f"{count} fehlgeschlagene Anmeldungen von **{plain(ip, 64)}** "
                    f"in {FAILED_LOGIN_WINDOW // 60} Minuten.",
                    f"Zuletzt für: {plain(email)}",
                ],
                "warning",
            )
        except Exception:  # noqa: BLE001
            _log.warning("platform bot: failed-login ping not queued", exc_info=True)


def old_keys(now: datetime | None = None) -> list[str]:
    """Encryption keys whose newest version is older than a year."""
    from sqlalchemy import func, select

    from hubra.core.extensions import db
    from hubra.core.models.data_key import DataKey

    now = now or datetime.now(timezone.utc)
    rows = db.session.execute(
        select(DataKey.scope, func.max(DataKey.created_at)).group_by(DataKey.scope)
    ).all()
    out = []
    for scope, newest in rows:
        if newest is None:
            continue
        if newest.tzinfo is None:
            newest = newest.replace(tzinfo=timezone.utc)
        if now - newest > timedelta(days=KEY_MAX_AGE_DAYS):
            out.append(scope)
    return sorted(out)


def key_reminder(now: datetime | None = None) -> bool:
    """Once a month: remind to rotate keys that are over a year old."""
    now = now or datetime.now(timezone.utc)
    scopes = old_keys(now)
    if not scopes:
        return False
    if not _set(f"platform_bot:keys:{now:%Y-%m}", "1", ex=40 * 24 * 3600, nx=True):
        return False
    platform = "p" in scopes
    clubs = len([s for s in scopes if s != "p"])
    lines = []
    if platform:
        lines.append("Der Plattform-Schlüssel ist über ein Jahr alt.")
    if clubs:
        lines.append(f"{clubs} Vereins-Schlüssel sind über ein Jahr alt.")
    lines.append(
        "Erneuern mit `flask crypto rotate --new-keys`; der Stand steht in "
        "manage › Plattform-Einstellungen › Verschlüsselung."
    )
    return post_security_now("Schlüssel erneuern", lines)
