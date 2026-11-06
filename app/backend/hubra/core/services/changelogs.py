"""Release notes of Hubra and its plugins for the clubs (and Hubra's server).

``announce`` (every minute, from the platform bot's tick) compares what runs
now with what was announced before: the Hubra version, and the version of
every loaded plugin. Each new one is sent once:

* in every active club as the contract event ``hubra.released`` /
  ``plugin.released`` (a plugin's only in the clubs that have it on), with
  that version's changelog section. The Discord plugin posts it on the
  club's server when the club opted in, in the channel it picked. Plugins
  get events through the contract outbox, so the delivery is stored in the
  same transaction as the "announced" mark below;
* to the changelog channel on Hubra's own Discord server
  (``discord.changelog_channel_id``), when one is set.

"Announced" is a ``changelog.sent`` row in the platform log per
``hubra@<version>`` / ``<plugin id>@<version>``, written in the same
transaction as the outbox rows: a version is either sent and marked, or
neither, and a version that is marked is never sent again (also not after
a rollback to it). The first run of an existing install only marks the
plugins that run now (``changelog.baseline``), so turning this on doesn't
post every plugin's current notes; Hubra's own version counts as sent when
the platform log already announced it (``release.announced``).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from hubra.core.extensions import db

_log = logging.getLogger(__name__)

SENT = "changelog.sent"
BASELINE = "changelog.baseline"
HUBRA = "hubra"
LOCK = "changelogs:announce"
# Discord lets a nonce be at most 25 characters.
NONCE_LENGTH = 25


def key(source: str, version: str) -> str:
    return f"{source}@{version}"


def nonce(*parts: object) -> str:
    """A Discord nonce for one post: the same parts give the same nonce."""
    raw = ":".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:NONCE_LENGTH]


# ── What runs now ───────────────────────────────────────────────────────────


def hubra_release() -> dict | None:
    """The running Hubra version with its changelog section (``hubra.released``)."""
    from hubra.core.services.version import VersionService

    version = VersionService.get_version()
    if not version:
        return None
    english = _entry(VersionService.get_changelog("en"), version)
    german = _entry(VersionService.get_changelog("de"), version)
    return {
        "version": str(version),
        "date": (english or {}).get("date"),
        "sections": (english or {}).get("sections") or {},
        "sections_de": (german or {}).get("sections") or {}
        if (german or {}).get("lang") == "de"
        else {},
    }


def _entry(entries: list[dict], version: str) -> dict | None:
    for entry in entries:
        if str(entry.get("version")) == str(version):
            return entry
    return None


def plugin_releases() -> list[dict]:
    """Every loaded plugin with its version and that version's notes."""
    from hubra.core.plugins import loader
    from hubra.core.plugins.installer import changes_for

    out = []
    for spec in loader.current().loaded():
        if not spec.version:
            continue
        try:
            notes = changes_for(spec.changelog(), spec.version)
        except OSError:
            notes = ""
        out.append(
            {
                "plugin_id": spec.id,
                "name": spec.name,
                "version": spec.version,
                "notes": notes,
                "modules": list(spec.module_codes),
            }
        )
    return out


# ── What was announced ──────────────────────────────────────────────────────


def _rows(kind: str):
    from hubra.core.models.platform_event import PlatformEvent

    return db.session.scalars(
        select(PlatformEvent).where(PlatformEvent.kind == kind)
    ).all()


def sent_keys() -> set[str]:
    return {r.message for r in _rows(SENT)} | {r.message for r in _rows(BASELINE)}


def _hubra_announced_before(version: str) -> bool:
    """The platform log announced *version* (before this module existed)."""
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


def _previous_version(plugin_id: str) -> str | None:
    """The plugin's version announced last (for "2.1.0 → 2.2.0")."""
    from hubra.core.models.platform_event import PlatformEvent

    row = db.session.scalar(
        select(PlatformEvent)
        .where(PlatformEvent.kind.in_((SENT, BASELINE)))
        .where(PlatformEvent.message.like(f"{plugin_id}@%"))
        .order_by(PlatformEvent.created_at.desc(), PlatformEvent.id.desc())
        .limit(1)
    )
    return row.message.partition("@")[2] if row is not None else None


def _mark(kind: str, message: str, details: dict | None = None) -> None:
    """In the caller's transaction (``platform_monitor.record`` commits on
    its own connection, which would split the mark from the outbox rows)."""
    from hubra.core.models.platform_event import PlatformEvent

    db.session.add(
        PlatformEvent(
            created_at=datetime.now(timezone.utc),
            category="system",
            kind=kind,
            level="info",
            message=message[:2000],
            details=details or {},
        )
    )


# ── Sending ─────────────────────────────────────────────────────────────────


def _clubs():
    from hubra.core.models.tenant import Tenant

    return db.session.scalars(
        select(Tenant).where(Tenant.status == "active").order_by(Tenant.id)
    ).all()


def _emit_everywhere(event: str, payload: dict, modules: list[str] | None) -> int:
    """Emit *event* in every active club (with one of *modules* on, if given).
    Returns in how many clubs someone listens."""
    from hubra.core.modules import is_enabled
    from hubra.core.modules.events import emit

    reached = 0
    for tenant in _clubs():
        if modules is not None and not any(
            is_enabled(code, tenant_id=tenant.id) for code in modules
        ):
            continue
        if emit(event, tenant_id=tenant.id, **payload):
            reached += 1
    return reached


def _to_platform_server(kind: str, payload: dict, mark: str) -> None:
    """Queue the post to Hubra's own changelog channel (after the commit)."""
    from hubra.core.services import platform_discord

    if not platform_discord.changelog_channel():
        return
    from hubra.core.tasks.after_commit import delay_after_commit
    from hubra.core.tasks.platform_bot_tasks import post_changelog

    delay_after_commit(post_changelog, kind, payload, nonce("platform", mark))


def announce() -> int:
    """Send every Hubra or plugin version not announced yet. Returns how many."""
    from hubra.core.modules.events import HUBRA_RELEASED, PLUGIN_RELEASED
    from hubra.core.services import platform_bot

    # One process at a time (several beat ticks or workers).
    if not platform_bot._set(LOCK, "1", ex=300, nx=True):
        return 0
    try:
        sent = sent_keys()
        plugins = plugin_releases()
        first_run = not sent
        done = 0

        hubra = hubra_release()
        if hubra is not None:
            mark = key(HUBRA, hubra["version"])
            if mark not in sent:
                if first_run and _hubra_announced_before(hubra["version"]):
                    _mark(BASELINE, mark)
                else:
                    _mark(SENT, mark, {"version": hubra["version"]})
                    reached = _emit_everywhere(HUBRA_RELEASED, hubra, None)
                    _to_platform_server("hubra", hubra, mark)
                    _log.info(
                        "changelog: Hubra %s to %d clubs", hubra["version"], reached
                    )
                    done += 1
                db.session.commit()

        for plugin in plugins:
            mark = key(plugin["plugin_id"], plugin["version"])
            if mark in sent:
                continue
            if first_run:
                _mark(BASELINE, mark)
                db.session.commit()
                continue
            payload = {
                "plugin_id": plugin["plugin_id"],
                "name": plugin["name"],
                "version": plugin["version"],
                "previous_version": _previous_version(plugin["plugin_id"]),
                "notes": plugin["notes"],
            }
            _mark(SENT, mark, {"version": plugin["version"]})
            reached = _emit_everywhere(PLUGIN_RELEASED, payload, plugin["modules"])
            _to_platform_server("plugin", payload, mark)
            _log.info(
                "changelog: %s %s to %d clubs",
                plugin["plugin_id"],
                plugin["version"],
                reached,
            )
            db.session.commit()
            done += 1
        return done
    except Exception:
        db.session.rollback()
        raise
    finally:
        platform_bot._delete(LOCK)


# ── Hubra's own server ──────────────────────────────────────────────────────

VIOLET = 0x6D4AFF


def _bullets(items: list[str], limit: int = 8, more: str = "more") -> str:
    text = "\n".join(f"• {i}" for i in items[:limit])
    if len(items) > limit:
        text += f"\n… {len(items) - limit} {more}"
    return text


def plugin_embed(payload: dict) -> dict:
    """``plugin.released`` as an embed for Hubra's changelog channel."""
    previous = payload.get("previous_version")
    version = str(payload.get("version") or "")
    title = f"{payload.get('name') or payload.get('plugin_id')} {version}"
    lines = [f"{previous} → {version}"] if previous and previous != version else []
    notes = str(payload.get("notes") or "").strip()
    if notes:
        lines.append(notes)
    return {
        "title": title[:256],
        "description": "\n\n".join(lines)[:3500] or "–",
        "color": VIOLET,
        "footer": {"text": "Hubra · plugins"},
    }


def post_to_platform(kind: str, payload: dict, post_nonce: str = "") -> bool:
    """Post one release note to Hubra's changelog channel."""
    from hubra.core.services import platform_bot, platform_discord

    channel = platform_discord.changelog_channel()
    _, token = platform_discord._settings()
    if not channel or not token:
        return False
    if kind == "hubra":
        embed = platform_bot.release_embed(
            str(payload.get("version") or ""),
            {
                "date": payload.get("date"),
                "sections": payload.get("sections_de") or payload.get("sections") or {},
            },
        )
    else:
        embed = plugin_embed(payload)
    platform_discord.post(embed, channel_id=channel, token=token, nonce=post_nonce)
    return True
