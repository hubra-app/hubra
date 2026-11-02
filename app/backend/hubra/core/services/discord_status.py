"""The Discord bot's state for manage › Diagnostics › Discord.

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
            "Portal and save the new one in Platform settings › Discord",
            403: "Discord refused access (403)",
            404: "Not found (404)",
            429: "Rate limited by Discord (429); try again in a minute",
        }.get(exc.code, f"Discord answered {exc.code}")
    return f"Discord unreachable: {exc}"


def _api_base() -> str:
    """The API's public address: API_PUBLIC_URL, else this request's host."""
    from flask import has_request_context, request

    base = current_app.config.get("API_PUBLIC_URL") or ""
    if not base and has_request_context():
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
    """Everything the Diagnostics › Discord tab shows."""
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
