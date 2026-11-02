"""Platform log on Discord: the Hubra bot posts platform events to a channel
on the platform's own Discord server.

What is posted:
  * every platform audit entry (``GlobalAuditEntry``: club created or
    suspended, club requests, platform roles, impersonation, plugins,
    backups, platform settings, ...), sorted into categories that the
    platform turns on or off (``discord.log_events``);
  * system alerts from ``services.alerts`` (failed tasks, API error rate,
    infrastructure checks), category ``alerts``.

Set up in manage › Platform settings › Discord: the bot token from the
Discord application (``discord.bot_token``), the bot added to the platform
server, and the channel ID (``discord.log_channel_id``).  No channel, no
posts.

Audit entries are posted by a Celery task queued after the commit, so a
rolled back change is never posted and a slow Discord never slows a
request.  The task gets the entry id only and reads the token itself.
Embeds carry the action, club, actor and target, plus the entry's details
minus anything that looks like a secret.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from sqlalchemy import event, select

from hubra.core.models.platform_setting import PlatformSetting
from hubra.core.models.tenant import GlobalAuditEntry

_log = logging.getLogger(__name__)

API = "https://discord.com/api/v10"
CHANNEL_KEY = "discord.log_channel_id"
EVENTS_KEY = "discord.log_events"

# Category → label (manage shows these).  ``members`` is off by default:
# every member who joins a club would be a post.
CATEGORIES: dict[str, str] = {
    "clubs": "Clubs created, changed, suspended or deleted; modules; domains",
    "requests": "Club requests submitted or rejected",
    "access": "Platform roles, club owners/admins added or removed, impersonation",
    "members": "Members added to a club or accepting an invite",
    "plugins": "Plugins installed, updated, removed; plugin repositories",
    "backups": "Backups created, verified, restored or deleted",
    "platform": "Platform settings, encryption keys, mail server, translations",
    "alerts": "System alerts: failed tasks, error rate, infrastructure checks",
    "digest": "Daily overview at 08:00: new clubs, sign-ups, mail, open problems",
    "releases": "A new Hubra version is running, with its release notes",
    "security": "Platform admins on new devices or without two-factor, "
    "many failed sign-ins from one address, old encryption keys",
}

# Bot permissions the platform server needs: view channel, send messages,
# embed links.
BOT_PERMISSIONS = (1 << 10) | (1 << 11) | (1 << 14)

COLOR_INFO = 0x6D4AFF  # Hubra violet
COLOR_GOOD = 0x2ECC71
COLOR_WARN = 0xF39C12
COLOR_BAD = 0xE74C3C

_SECRET_WORDS = ("password", "secret", "token", "key", "otp", "code")


def category(action: str) -> str:
    """The category an audit action belongs to."""
    a = action or ""
    if a.startswith("tenant_request."):
        return "requests"
    if a.startswith(("impersonation.", "global_role.")) or (
        a.startswith(("tenant.add_", "tenant.remove_")) and a != "tenant.add_member"
    ):
        return "access"
    if a in ("tenant.add_member", "tenant.invite_accepted"):
        return "members"
    if a.startswith(("tenant.", "domain.")) or a in (
        "set_tenant_module",
        "club_settings.update",
        "bank_settings.update",
    ):
        return "clubs"
    if a.startswith("backup."):
        return "backups"
    if "plugin" in a:
        return "plugins"
    return "platform"


def _color(action: str) -> int:
    a = action or ""
    if any(w in a for w in ("delete", "suspend", "reject", "failed", "expired")):
        return COLOR_BAD
    if any(w in a for w in ("remove", "unverified", "impersonation.start")):
        return COLOR_WARN
    if any(w in a for w in ("provision", "approve", "active", "accepted", "install")):
        return COLOR_GOOD
    return COLOR_INFO


def enabled_categories() -> set[str]:
    from hubra.core.services import platform_settings

    raw = platform_settings.get(EVENTS_KEY)
    return {c.strip() for c in raw.split(",") if c.strip() in CATEGORIES}


def _settings() -> tuple[str, str]:
    """(channel id, bot token); either empty means the log is off."""
    from hubra.core.services import platform_settings

    return platform_settings.get(CHANNEL_KEY), platform_settings.discord().bot_token


# ── Posting ───────────────────────────────────────────────────────────────────


class DiscordPostError(RuntimeError):
    pass


def post(
    embed: dict,
    *,
    channel_id: str = "",
    token: str = "",
    components: list | None = None,
) -> dict:
    """Post one embed to the platform log channel.  Raises DiscordPostError.

    *components*: buttons under the message (``platform_bot``).  Returns
    Discord's message (``id``, ``channel_id``), or ``{}``.  The outcome is
    remembered for manage › Diagnostics › Discord.
    """
    try:
        message = _post(
            embed, channel_id=channel_id, token=token, components=components
        )
    except DiscordPostError as exc:
        _remember_post(False, str(exc))
        raise
    _remember_post(True, "")
    return message


def _post(
    embed: dict,
    *,
    channel_id: str = "",
    token: str = "",
    components: list | None = None,
) -> dict:
    if not channel_id or not token:
        channel_id, token = _settings()
    if not channel_id or not token:
        raise DiscordPostError("Set the bot token and the log channel first")
    payload: dict[str, Any] = {"embeds": [embed], "allowed_mentions": {"parse": []}}
    if components:
        payload["components"] = components
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{API}/channels/{channel_id}/messages",
        data=body,
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
            "User-Agent": "Hubra (https://hubra.club, 1.0)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            if resp.status not in (200, 201):
                raise DiscordPostError(f"Discord answered {resp.status}")
            try:
                message = json.loads(resp.read() or b"{}")
            except (TypeError, ValueError):
                return {}
            return message if isinstance(message, dict) else {}
    except urllib.error.HTTPError as exc:
        hint = {
            401: "the bot token is wrong",
            403: "the bot cannot post in that channel (add it to the server "
            "and give it View Channel, Send Messages and Embed Links)",
            404: "no channel with that ID",
        }.get(exc.code, f"Discord answered {exc.code}")
        raise DiscordPostError(hint) from None
    except DiscordPostError:
        raise
    except Exception as exc:
        raise DiscordPostError(f"Discord unreachable: {exc}") from None


_LAST_POST_KEY = "discord:platform_log:last"
_local_last: dict[str, dict] = {}


def _remember_post(ok: bool, error: str) -> None:
    """Keep the last success and the last failure (Redis, else this process)."""
    from datetime import datetime, timezone

    from hubra.core.redis_client import get_redis_client

    now = datetime.now(timezone.utc).isoformat()
    state = dict(last_post_state())
    if ok:
        state["lastOkAt"] = now
    else:
        state["lastErrorAt"] = now
        state["lastError"] = error[:500]
    _local_last["state"] = state
    try:
        client = get_redis_client()
        if client is not None:
            client.set(_LAST_POST_KEY, json.dumps(state), ex=30 * 24 * 3600)
    except Exception:
        pass


def last_post_state() -> dict:
    """``{"lastOkAt"?, "lastErrorAt"?, "lastError"?}`` of the platform log."""
    from hubra.core.redis_client import get_redis_client

    try:
        client = get_redis_client()
        if client is not None:
            raw = client.get(_LAST_POST_KEY)
            if raw:
                return json.loads(raw)
    except Exception:
        pass
    return dict(_local_last.get("state") or {})


def post_alert(embed: dict, alert_type: str = "system") -> bool:
    """Post a system alert if the log is set up and ``alerts`` is on, with
    buttons to acknowledge it, silence its type for an hour and open manage
    (``platform_bot``).  Never raises: alerts run from failure handlers.
    """
    try:
        from flask import has_app_context

        if not has_app_context():
            return False
        channel_id, token = _settings()
        if not channel_id or not token or "alerts" not in enabled_categories():
            return False
        from hubra.core.services import platform_bot

        message = post(
            embed,
            channel_id=channel_id,
            token=token,
            components=platform_bot.alert_buttons(alert_type),
        )
        platform_bot.track_alert(message, alert_type)
        return True
    except Exception:
        _log.warning("Platform Discord alert failed", exc_info=True)
        return False


# ── Audit entries ─────────────────────────────────────────────────────────────


def _secret(key: Any) -> bool:
    return any(w in str(key).lower() for w in _SECRET_WORDS)


def _clean(value: Any, depth: int = 0) -> Any:
    """Details without secret-looking keys, cut to a sensible size."""
    if isinstance(value, dict):
        if depth >= 2:
            return "…"
        return {
            k: "***" if _secret(k) else _clean(v, depth + 1) for k, v in value.items()
        }
    if isinstance(value, list):
        return [_clean(v, depth + 1) for v in value[:10]]
    return value


def _field_value(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return (text or "–")[:1000]


def audit_embed(entry: GlobalAuditEntry) -> dict:
    """The embed for one audit entry."""
    from hubra.core.extensions import db
    from hubra.core.models.tenant import Tenant
    from hubra.core.models.user import User

    fields: list[dict] = []
    if entry.tenant_id:
        tenant = db.session.get(Tenant, entry.tenant_id)
        club = f"{tenant.name} ({tenant.slug})" if tenant else f"#{entry.tenant_id}"
        fields.append({"name": "Club", "value": club[:1000], "inline": True})
    if entry.actor_id:
        user = db.session.get(User, entry.actor_id)
        fields.append(
            {
                "name": "By",
                "value": (user.email if user else f"user #{entry.actor_id}")[:1000],
                "inline": True,
            }
        )
    if entry.target_type or entry.target_id:
        target = " ".join(x for x in (entry.target_type, entry.target_id) if x)
        fields.append({"name": "Target", "value": target[:1000], "inline": True})
    for key, value in list((_clean(entry.details or {}) or {}).items())[:10]:
        fields.append(
            {"name": str(key)[:250], "value": _field_value(value), "inline": True}
        )

    embed: dict[str, Any] = {
        "title": entry.action[:250],
        "color": _color(entry.action),
        "fields": fields[:25],
        "footer": {"text": f"Hubra platform · {category(entry.action)}"},
    }
    if entry.time:
        embed["timestamp"] = entry.time.isoformat()
    return embed


def post_audit_entry(entry_id: int) -> bool:
    """Post one audit entry if its category is on.  Used by the task."""
    from hubra.core.extensions import db

    entry = db.session.get(GlobalAuditEntry, entry_id)
    if entry is None:
        return False
    channel_id, token = _settings()
    if not channel_id or not token:
        return False
    from hubra.core.services import platform_bot

    # A decision on a club request also updates the request's own message.
    platform_bot.request_decided(entry)
    if category(entry.action) not in enabled_categories():
        return False
    components = platform_bot.request_buttons(entry)
    message = post(
        audit_embed(entry),
        channel_id=channel_id,
        token=token,
        components=components,
    )
    if components:
        platform_bot.track_request(entry, message)
    return True


@event.listens_for(GlobalAuditEntry, "after_insert")
def _queue_audit_entry(mapper, connection, target) -> None:
    """Queue the post after the commit, but only when a channel is set.

    Reads the channel row on the flush's own connection, so an instance
    without a log channel queues nothing.
    """
    try:
        channel = connection.execute(
            select(PlatformSetting.value).where(PlatformSetting.key == CHANNEL_KEY)
        ).scalar()
    except Exception:
        _log.debug("platform log: could not read the channel setting", exc_info=True)
        return
    if not channel:
        return
    from hubra.core.tasks.after_commit import delay_after_commit
    from hubra.core.tasks.platform_discord_tasks import post_platform_audit_entry

    delay_after_commit(post_platform_audit_entry, target.id)
