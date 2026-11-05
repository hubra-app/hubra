"""The Discord bot's state for manage › Discord › Status.

What it checks:
  * the application settings (ID, public key, client secret, bot token);
  * the bot's sign-in, live: ``GET /users/@me`` with the bot token, plus the
    servers it is on and the application's Interactions Endpoint URL
    (``GET /applications/@me``) compared with the one Hubra expects;
  * the platform log: channel set and reachable, categories, last post and
    last failure (``platform_discord.last_post_state``);
  * the Discord plugin and the club servers connected through it
    (``connected_apps``), with each one's last use and last error;
  * how many accounts are linked.

The live check is kept for ``CHECK_TTL`` (Redis, else per process), so the
page and the alerts overview don't call Discord on every load; "Check now"
runs it again.  The token never leaves the server.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from flask import current_app
from sqlalchemy import func, select

from hubra.core.extensions import db

_log = logging.getLogger(__name__)

CHECK_TTL = 300  # seconds
_CHECK_KEY = "discord:bot:check"
_local: dict[str, dict] = {}


def _api(path: str, token: str) -> object:
    from hubra.core.services.platform_discord import API

    req = urllib.request.Request(
        f"{API}{path}",
        headers={
            "Authorization": f"Bot {token}",
            "User-Agent": "Hubra (https://hubra.club, 1.0)",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
        return json.loads(resp.read() or b"null")


def _error_text(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return {
            401: "Discord refused the bot token (401): reset it in the Developer "
            "Portal and save the new one in Discord › Setup",
            403: "Discord refused access (403)",
            404: "Not found (404)",
            429: "Rate limited by Discord (429); try again in a minute",
        }.get(exc.code, f"Discord answered {exc.code}")
    _log.warning("Discord check failed: %s", exc)
    return "Discord unreachable; see the server log for details"


def _api_base() -> str:
    """The API's public address: API_PUBLIC_URL, else this request's host.

    Not the host of a request made with an API token: the Claude connector
    calls the backend inside the cluster (``http://platform-backend:5000``),
    and that address is no use in Discord's Developer Portal.  Unknown
    (empty) then, like without a request.
    """
    from flask import g, has_request_context, request

    base = current_app.config.get("API_PUBLIC_URL") or ""
    if not base and has_request_context() and not getattr(g, "api_token", None):
        base = request.host_url
    return base.rstrip("/")


def expected_interactions_url() -> str:
    base = _api_base()
    return f"{base}/api/v1/discord/interactions" if base else ""


def redirect_uris() -> list[str]:
    """The two OAuth2 redirects the Developer Portal must list."""
    base = _api_base()
    if not base:
        return []
    return [
        f"{base}/api/v1/apps/callback/discord",
        f"{base}/api/v1/account/linked-accounts/discord/callback",
    ]


def linked_roles_url() -> str:
    """General Information › Linked Roles Verification URL: where Discord
    sends someone who picks a Hubra linked role."""
    from hubra.core.services.email import _get_sso_base_url

    base = _get_sso_base_url()
    return f"{base}/account/verknuepfungen?link=discord" if base else ""


def _redis():
    from hubra.core.redis_client import get_redis_client

    return get_redis_client()


def last_check() -> dict | None:
    client = _redis()
    if client is not None:
        try:
            raw = client.get(_CHECK_KEY)
            if raw:
                return json.loads(raw)
        except Exception:
            pass
    return _local.get("check")


def _store(result: dict) -> None:
    _local["check"] = result
    client = _redis()
    if client is not None:
        try:
            client.set(_CHECK_KEY, json.dumps(result), ex=24 * 3600)
        except Exception:
            pass


def run_check() -> dict:
    """Ask Discord now: bot sign-in, servers, interactions URL, log channel."""
    from hubra.core.services import platform_discord, platform_settings

    app = platform_settings.discord()
    channel_id = platform_settings.get(platform_discord.CHANNEL_KEY)
    result: dict = {
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "checkedAtTs": time.time(),
        "botOk": None,
    }
    if not app.bot_token:
        _store(result)
        return result

    try:
        me = _api("/users/@me", app.bot_token) or {}
        result["botOk"] = True
        result["botUser"] = {
            "id": str(me.get("id") or ""),
            "username": str(me.get("username") or ""),
        }
    except Exception as exc:
        result["botOk"] = False
        result["botError"] = _error_text(exc)
        _store(result)
        return result

    try:
        guilds = _api("/users/@me/guilds?limit=200", app.bot_token) or []
        result["guildCount"] = len(guilds) if isinstance(guilds, list) else None
        result["guildIds"] = [str(g.get("id")) for g in guilds if isinstance(g, dict)][
            :200
        ]
    except Exception as exc:
        result["guildError"] = _error_text(exc)

    try:
        application = _api("/applications/@me", app.bot_token) or {}
        result["interactionsUrl"] = str(
            application.get("interactions_endpoint_url") or ""
        )
        if app.client_id and str(application.get("id") or "") != app.client_id:
            result["appIdMismatch"] = str(application.get("id") or "")
    except Exception as exc:
        result["interactionsError"] = _error_text(exc)

    if channel_id:
        try:
            channel = _api(f"/channels/{channel_id}", app.bot_token) or {}
            result["channelOk"] = True
            result["channelName"] = str(channel.get("name") or "")
        except Exception as exc:
            result["channelOk"] = False
            result["channelError"] = (
                "The bot cannot see that channel: add the bot to the platform "
                "server and allow it to view the channel"
                if isinstance(exc, urllib.error.HTTPError) and exc.code in (403, 404)
                else _error_text(exc)
            )
    _store(result)
    return result


def check(refresh: bool = False) -> dict:
    """The last live check, run again when asked or older than CHECK_TTL."""
    last = last_check()
    if (
        refresh
        or last is None
        or time.time() - float(last.get("checkedAtTs") or 0) > CHECK_TTL
    ):
        return run_check()
    return last


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def status(refresh: bool = False) -> dict:
    """Everything the Discord › Status tab shows."""
    from hubra.core.models.connected_app import ConnectedApp, ExternalAccount
    from hubra.core.models.plugin import InstalledPlugin
    from hubra.core.models.tenant import Tenant
    from hubra.core.services import platform_discord, platform_settings

    app = platform_settings.discord()
    settings = {
        "clientId": bool(app.client_id),
        "publicKey": bool(app.public_key),
        "clientSecret": bool(app.client_secret),
        "botToken": bool(app.bot_token),
    }
    live = check(refresh) if app.bot_token else {"botOk": None}

    plugin = db.session.get(InstalledPlugin, "discord")
    rows = db.session.execute(
        select(ConnectedApp, Tenant.name, Tenant.slug)
        .join(Tenant, Tenant.id == ConnectedApp.tenant_id)
        .where(ConnectedApp.provider == "discord", ConnectedApp.status != "revoked")
        .order_by(Tenant.name)
    ).all()
    guild_ids = set(live.get("guildIds") or [])
    servers = [
        {
            "id": conn.id,
            "club": name,
            "clubSlug": slug,
            "server": conn.label or conn.external_id,
            "serverId": conn.external_id,
            "status": conn.status,
            # None when the guild list could not be read.
            "botOnServer": (conn.external_id in guild_ids)
            if live.get("guildIds") is not None
            else None,
            "lastUsedAt": _iso(conn.last_used_at),
            "lastError": conn.last_error,
            "lastErrorAt": _iso(conn.last_error_at),
        }
        for conn, name, slug in rows
    ]
    linked = db.session.scalar(
        select(func.count())
        .select_from(ExternalAccount)
        .where(ExternalAccount.provider == "discord")
    )

    channel_id = platform_settings.get(platform_discord.CHANNEL_KEY)
    return {
        "settings": settings,
        "configured": settings["clientId"] and settings["botToken"],
        "check": {k: v for k, v in live.items() if k != "guildIds"},
        "interactions": {
            "expected": expected_interactions_url(),
            "actual": live.get("interactionsUrl"),
        },
        "redirectUris": redirect_uris(),
        "linkedRolesUrl": linked_roles_url(),
        "platformLog": {
            "channelId": channel_id,
            "categories": sorted(platform_discord.enabled_categories()),
            **platform_discord.last_post_state(),
        },
        "plugin": {
            "installed": plugin is not None,
            "version": getattr(plugin, "version", None),
            "error": getattr(plugin, "error", "") or "",
        },
        "servers": servers,
        "linkedAccounts": int(linked or 0),
    }


def _ts(iso: str | None) -> float | None:
    try:
        return datetime.fromisoformat(iso).timestamp() if iso else None
    except ValueError:
        return None


def problems() -> list[dict]:
    """Discord problems for the alerts overview, from stored state only.

    ``since`` is a Unix timestamp, like the other open problems.
    """
    from hubra.core.services import platform_discord

    out: list[dict] = []
    last = last_check() or {}
    if last.get("botOk") is False:
        out.append(
            {
                "id": "discord:bot",
                "level": "error",
                "title": "The Discord bot cannot sign in",
                "detail": last.get("botError") or "",
                "since": last.get("checkedAtTs"),
            }
        )
    elif last.get("channelOk") is False:
        out.append(
            {
                "id": "discord:channel",
                "level": "warning",
                "title": "The bot cannot see the platform log channel",
                "detail": last.get("channelError") or "",
                "since": last.get("checkedAtTs"),
            }
        )
    state = platform_discord.last_post_state()
    if state.get("lastErrorAt") and state.get("lastErrorAt") > (
        state.get("lastOkAt") or ""
    ):
        out.append(
            {
                "id": "discord:log",
                "level": "warning",
                "title": "Posts to the platform Discord log fail",
                "detail": state.get("lastError") or "",
                "since": _ts(state.get("lastErrorAt")),
            }
        )
    return out


# ── Picking the platform log server and channel ─────────────────────────────

_VIEW, _SEND, _EMBED, _ADMIN = 1 << 10, 1 << 11, 1 << 14, 1 << 3
_POST = _VIEW | _SEND | _EMBED
_TEXT_CHANNELS = (0, 5)


class PickerError(Exception):
    pass


def _token() -> str:
    from hubra.core.services.platform_settings import discord

    token = discord().bot_token
    if not token:
        raise PickerError("Set the bot token first")
    return token


def _call(path: str, token: str):
    try:
        return _api(path, token)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise PickerError(_error_text(exc)) from exc


def servers() -> dict:
    """The servers the bot is on, and the one the log channel is on."""
    from hubra.core.services import platform_settings

    token = _token()
    guilds = _call("/users/@me/guilds?limit=200", token) or []
    current = None
    # Log and audit channel share one server: preselect it from either.
    channel_id = platform_settings.get(
        "discord.log_channel_id"
    ) or platform_settings.get("discord.audit_channel_id")
    if channel_id:
        try:
            current = (_api(f"/channels/{channel_id}", token) or {}).get("guild_id")
        except Exception:
            current = None  # gone or not visible: nothing preselected
    return {
        "servers": sorted(
            (
                {
                    "id": str(g["id"]),
                    "name": g.get("name", ""),
                    "icon": (
                        f"https://cdn.discordapp.com/icons/{g['id']}/{g['icon']}.png?size=64"
                        if g.get("icon")
                        else None
                    ),
                }
                for g in guilds
            ),
            key=lambda g: g["name"].lower(),
        ),
        "currentServerId": str(current) if current else None,
    }


def _overwrite(bits: int, ow: dict | None) -> int:
    if not ow:
        return bits
    return (bits & ~int(ow.get("deny") or 0)) | int(ow.get("allow") or 0)


def can_post(
    channel: dict, guild_id: str, base: int, role_ids: set[str], me: str
) -> bool:
    """Whether the bot may view, send and embed in *channel* (Discord's
    permission order: @everyone, roles, the member)."""
    if base & _ADMIN:
        return True
    bits = base
    overwrites = {str(o["id"]): o for o in channel.get("permission_overwrites") or []}
    bits = _overwrite(bits, overwrites.get(str(guild_id)))
    deny = allow = 0
    for rid in role_ids:
        o = overwrites.get(rid)
        if o and o.get("type") in (0, "0"):
            deny |= int(o.get("deny") or 0)
            allow |= int(o.get("allow") or 0)
    bits = (bits & ~deny) | allow
    member = overwrites.get(str(me))
    if member and member.get("type") in (1, "1"):
        bits = _overwrite(bits, member)
    return bits & _POST == _POST


def channels(guild_id: str) -> list[dict]:
    """The server's text channels the bot can post in, in Discord's order."""
    from hubra.core.services.platform_settings import discord

    if not str(guild_id).isdigit():
        raise PickerError("Unknown server")
    token = _token()
    me = discord().client_id or (_call("/users/@me", token) or {}).get("id", "")
    roles = {
        str(r["id"]): int(r.get("permissions") or 0)
        for r in _call(f"/guilds/{guild_id}/roles", token) or []
    }
    member = _call(f"/guilds/{guild_id}/members/{me}", token) or {}
    role_ids = {str(r) for r in member.get("roles", [])}
    base = roles.get(str(guild_id), 0)
    for rid in role_ids:
        base |= roles.get(rid, 0)
    all_channels = _call(f"/guilds/{guild_id}/channels", token) or []
    categories = {
        str(c["id"]): c.get("name", "") for c in all_channels if c.get("type") == 4
    }
    out = [
        {
            "id": str(c["id"]),
            "name": c.get("name", ""),
            "category": categories.get(str(c.get("parent_id") or "")),
            "_pos": (
                next(
                    (
                        p.get("position", 0)
                        for p in all_channels
                        if str(p["id"]) == str(c.get("parent_id") or "")
                    ),
                    -1,
                ),
                c.get("position", 0),
            ),
        }
        for c in all_channels
        if c.get("type") in _TEXT_CHANNELS
        and can_post(c, str(guild_id), base, role_ids, str(me))
    ]
    out.sort(key=lambda c: c.pop("_pos"))
    return out


# ── Manage › Discord › Server: every club's bot ─────────────────────────────

# What a club turned on, as short labels for the overview (config key, scope
# it needs, label).  Read from the connection's config: the plugin's own
# defaults apply when a key is missing.
_FEATURES = (
    ("announce_events", "announce", True, "Anlässe"),
    ("announce_posts", "announce", True, "Beiträge"),
    ("announce_polls", "announce", False, "Umfragen"),
    ("announce_reminders", "announce", False, "Erinnerungen"),
    ("discord_events", "events", True, "Discord-Events"),
    ("poll_buttons", "commands", True, "Abstimmknöpfe"),
    ("self_checkin", "commands", True, "Einchecken"),
    ("group_roles", "roles", False, "Gruppenrollen"),
    ("welcome_dm", "notify", False, "Begrüssung"),
    ("hubra_news", "announce", False, "Hubra-News"),
)
OVERVIEW_DAYS = 7


def _features(conn) -> list[str]:
    config = conn.config or {}
    scopes = set(conn.scopes or [])
    out = [
        label
        for key, scope, default, label in _FEATURES
        if scope in scopes and config.get(key, default)
    ]
    if "roles" in scopes and config.get("role_map"):
        out.append(f"{len(config['role_map'])} Rollen-Zuordnungen")
    if "channels" in scopes and config.get("group_channels"):
        out.append(f"{len(config['group_channels'])} Gruppenkanäle")
    return out


def server_overview() -> dict:
    """Every club server the bot is on, for manage › Discord › Server.

    From stored state only (no Discord call per server): the connection,
    what the club turned on, the channels it picked, what the bot did in
    the last ``OVERVIEW_DAYS`` days and its last post and failure.
    """
    from datetime import timedelta

    from hubra.core.models.connected_app import ConnectedApp, ConnectedAppEvent
    from hubra.core.models.plugin import InstalledPlugin
    from hubra.core.models.tenant import Tenant

    since = datetime.now(timezone.utc) - timedelta(days=OVERVIEW_DAYS)
    rows = db.session.execute(
        select(ConnectedApp, Tenant)
        .join(Tenant, Tenant.id == ConnectedApp.tenant_id)
        .where(ConnectedApp.provider == "discord", ConnectedApp.status != "revoked")
        .order_by(Tenant.name)
    ).all()
    ids = [conn.id for conn, _ in rows]
    counts: dict[int, dict[str, int]] = {}
    last_post: dict[int, datetime] = {}
    if ids:
        for conn_id, ok, n in db.session.execute(
            select(
                ConnectedAppEvent.connection_id,
                ConnectedAppEvent.ok,
                func.count(),
            )
            .where(
                ConnectedAppEvent.connection_id.in_(ids),
                ConnectedAppEvent.created_at >= since,
            )
            .group_by(ConnectedAppEvent.connection_id, ConnectedAppEvent.ok)
        ):
            counts.setdefault(conn_id, {"ok": 0, "failed": 0})[
                "ok" if ok else "failed"
            ] += int(n)
        for conn_id, at in db.session.execute(
            select(
                ConnectedAppEvent.connection_id, func.max(ConnectedAppEvent.created_at)
            )
            .where(
                ConnectedAppEvent.connection_id.in_(ids),
                ConnectedAppEvent.action == "announced",
                ConnectedAppEvent.ok.is_(True),
            )
            .group_by(ConnectedAppEvent.connection_id)
        ):
            last_post[conn_id] = at

    live = last_check() or {}
    guild_ids = live.get("guildIds")
    plugin = db.session.get(InstalledPlugin, "discord")
    servers = []
    for conn, tenant in rows:
        config = conn.config or {}
        servers.append(
            {
                "id": conn.id,
                "club": tenant.name,
                "clubSlug": tenant.slug,
                "clubId": tenant.id,
                "clubActive": tenant.status == "active",
                "server": config.get("guild_name") or conn.label or conn.external_id,
                "serverId": conn.external_id,
                "status": conn.status,
                "botOnServer": (conn.external_id in guild_ids)
                if guild_ids is not None
                else None,
                "scopes": list(conn.scopes or []),
                "features": _features(conn),
                "mainChannel": bool(config.get("channel_id")),
                "logChannel": bool(config.get("log_channel_id")),
                "liveMessages": len(config.get("posted") or {}),
                "week": counts.get(conn.id, {"ok": 0, "failed": 0}),
                "lastPostAt": _iso(last_post.get(conn.id)),
                "lastUsedAt": _iso(conn.last_used_at),
                "lastError": conn.last_error,
                "lastErrorAt": _iso(conn.last_error_at),
                "connectedAt": _iso(conn.confirmed_at),
                "connectedBy": conn.created_by_name,
            }
        )
    return {
        "days": OVERVIEW_DAYS,
        "plugin": {
            "installed": plugin is not None,
            "version": getattr(plugin, "version", None),
        },
        "checkedAt": live.get("checkedAt"),
        "servers": servers,
        "totals": {
            "servers": len(servers),
            "active": sum(1 for s in servers if s["status"] == "active"),
            "withErrors": sum(1 for s in servers if s["week"]["failed"]),
            "botMissing": sum(1 for s in servers if s["botOnServer"] is False),
        },
    }


def server_activity(connection_id: int, limit: int = 100) -> dict | None:
    """One club server's bot log (the connection's activity list)."""
    from hubra.core import apps
    from hubra.core.models.connected_app import ConnectedApp
    from hubra.core.models.tenant import Tenant

    conn = db.session.get(ConnectedApp, connection_id)
    if conn is None or conn.provider != "discord":
        return None
    tenant = db.session.get(Tenant, conn.tenant_id)
    return {
        "id": conn.id,
        "club": tenant.name if tenant else "",
        "server": (conn.config or {}).get("guild_name") or conn.label,
        "events": [
            {
                "action": e.action,
                "ok": e.ok,
                "detail": e.detail,
                "at": _iso(e.created_at),
            }
            for e in apps.events(conn, limit=limit)
        ],
    }


# ── Making a platform channel through the bot ───────────────────────────────

_MANAGE_CHANNELS = 1 << 4
MAX_CHANNEL_NAME = 100


def channel_name(raw: str) -> str:
    """Discord's text channel form: lowercase, dashes, no spaces."""
    import re

    name = re.sub(r"[^\w-]+", "-", (raw or "").strip().lower(), flags=re.UNICODE)
    return re.sub(r"-{2,}", "-", name).strip("-")[:MAX_CHANNEL_NAME]


def create_channel(
    guild_id: str, name: str, *, private: bool = True, topic: str = ""
) -> dict:
    """A new text channel on one of the bot's servers (the platform log or
    audit channel).  Private: only the bot and the Plattform-Admin role
    (when platform roles are on) see it.  Raises PickerError."""
    from hubra.core.services import platform_bot, platform_roles
    from hubra.core.services.platform_settings import discord

    if not str(guild_id).isdigit():
        raise PickerError("Unknown server")
    clean = channel_name(name)
    if not clean:
        raise PickerError("Give the channel a name")
    _token()
    me = discord().client_id or ""
    body: dict = {"name": clean, "type": 0}
    if topic:
        body["topic"] = topic.strip()[:1024]
    if private:
        see = _VIEW | _SEND | _EMBED
        overwrites = [
            {"id": str(guild_id), "type": 0, "deny": str(_VIEW), "allow": "0"}
        ]
        if me:
            overwrites.append(
                {"id": str(me), "type": 1, "allow": str(see), "deny": "0"}
            )
        admin_role = platform_roles._stored_ids().get("platform_admin")
        if admin_role:
            overwrites.append(
                {"id": admin_role, "type": 0, "allow": str(_VIEW), "deny": "0"}
            )
        body["permission_overwrites"] = overwrites
    try:
        made = platform_bot._bot("POST", f"/guilds/{guild_id}/channels", body) or {}
    except platform_bot.BotError as exc:
        if getattr(exc, "status", None) == 403:
            raise PickerError(
                "The bot may not make channels on this server: give the Hubra "
                "role «Manage Channels» in the server settings"
            ) from None
        raise PickerError(str(exc)) from None
    return {"id": str(made.get("id", "")), "name": made.get("name", clean)}
