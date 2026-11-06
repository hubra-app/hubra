"""Discord direct messages to an account, outside any club.

Some news belongs to the person, not to a club: a sign-in to their account
from a new device, or an answer to a request they made (a support case, a
request for a new club). When the account linked Discord (Konto ›
Verknüpfungen), the platform's Hubra bot can send these as a direct message.

Every kind is off until the person turns it on (SSO › Konto ›
Benachrichtigungen), and one switch (``muted``) stops every Discord direct
message from Hubra, the club ones too (see ``channels``). The choices live in
``users.dm_prefs``: ``{"muted": bool, "<kind>": bool}``.

Discord only delivers a bot's direct message to someone who shares a server
with the bot (any club server with the Hubra bot) and allows direct messages
from that server's members; otherwise the message is dropped and logged.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from hubra.core.extensions import db

_log = logging.getLogger(__name__)

# The kinds an account can turn on, in the order the settings show them.
KINDS = ("sign_in", "requests")
COLOR = 0x6D3FD8
COLOR_WARN = 0xE8A33D


def discord_id(user_id: int) -> str | None:
    """The account's linked Discord user id, or None."""
    from hubra.core.models.connected_app import ExternalAccount

    return db.session.scalar(
        select(ExternalAccount.external_id).where(
            ExternalAccount.user_id == user_id,
            ExternalAccount.provider == "discord",
        )
    )


def bot_ready() -> bool:
    """Whether the platform has a Discord bot to send with."""
    from hubra.core.services import platform_settings

    try:
        return bool(platform_settings.discord().bot_token)
    except Exception:  # noqa: BLE001
        return False


def muted(user) -> bool:
    return bool((getattr(user, "dm_prefs", None) or {}).get("muted"))


def prefs_for(user) -> dict:
    """What the settings page shows."""
    stored = user.dm_prefs or {}
    return {
        "available": bot_ready() and discord_id(user.id) is not None,
        "muted": bool(stored.get("muted")),
        "kinds": {kind: stored.get(kind) is True for kind in KINDS},
    }


def validate(body) -> str | None:
    if not isinstance(body, dict) or not body:
        return "Expected an object"
    for key, value in body.items():
        if key == "kinds":
            if not isinstance(value, dict):
                return "kinds: expected an object"
            for kind, on in value.items():
                if kind not in KINDS:
                    return f"Unknown kind: {kind}"
                if not isinstance(on, bool):
                    return f"kinds.{kind}: true or false"
        elif key == "muted":
            if not isinstance(value, bool):
                return "muted: true or false"
        else:
            return f"Unknown field: {key}"
    return None


def apply(user, body: dict) -> None:
    """Store a validated body; what is left out keeps its value."""
    stored = dict(user.dm_prefs or {})
    if "muted" in body:
        stored["muted"] = body["muted"]
    for kind, on in (body.get("kinds") or {}).items():
        stored[kind] = on
    user.dm_prefs = {k: v for k, v in stored.items() if v is True} or None


def wants(user, kind: str) -> bool:
    """Whether *user* gets *kind* as a Discord direct message."""
    if user is None or kind not in KINDS or muted(user):
        return False
    return (user.dm_prefs or {}).get(kind) is True


def send(
    user,
    kind: str,
    embed: dict,
    components: list | None = None,
    *,
    now: bool = False,
) -> bool:
    """Queue *embed* as a direct message to *user* when they asked for
    *kind*: sent by the worker after the commit, or right away with *now*
    (for callers that committed already). True when queued."""
    if not wants(user, kind) or not bot_ready():
        return False
    external_id = discord_id(user.id)
    if not external_id:
        return False
    from hubra.core.tasks.after_commit import delay_after_commit
    from hubra.core.tasks.connected_app_tasks import send_account_dm

    try:
        if now:
            send_account_dm.delay(external_id, kind, embed, components)
        else:
            delay_after_commit(send_account_dm, external_id, kind, embed, components)
    except Exception:  # noqa: BLE001
        _log.warning("account dm not queued user_id=%s", user.id, exc_info=True)
        return False
    return True


def deliver(external_id: str, kind: str, embed: dict, components=None) -> bool:
    """In the worker: send it. A closed inbox is logged, not retried."""
    from hubra.core.services import platform_discord

    try:
        platform_discord.dm(external_id, embed, components=components)
    except platform_discord.DiscordPostError as exc:
        _log.info("account dm %s not sent: %s", kind, exc)
        return False
    return True


# ── The messages ─────────────────────────────────────────────────────────────


def _de(user) -> bool:
    return not str(getattr(user, "language", "") or "de").startswith("en")


def sign_in_embed(user, info: dict) -> tuple[dict, list]:
    """The new-device alert. *info*: what ``known_devices.sign_in_info``
    gathered (time, ip, device, method, second step, sessions, links)."""
    de = _de(user)
    fields = [
        ("Zeit" if de else "Time", info.get("time")),
        ("Gerät" if de else "Device", info.get("device")),
        ("IP-Adresse" if de else "IP address", info.get("ip")),
        ("Anmeldung mit" if de else "Signed in with", info.get("method")),
        ("Zweiter Schritt" if de else "Second step", info.get("second_step")),
        ("Aktive Sitzungen" if de else "Active sessions", info.get("sessions")),
    ]
    embed = {
        "title": "🔐 Neue Anmeldung bei deinem Konto"
        if de
        else "🔐 New sign-in to your account",
        "description": (
            "Jemand hat sich gerade von einem neuen Gerät oder Browser aus bei "
            "deinem Hubra-Konto angemeldet. Warst du das, musst du nichts tun."
            if de
            else "Someone just signed in to your Hubra account from a new device "
            "or browser. If this was you, there is nothing to do."
        ),
        "color": COLOR_WARN,
        "fields": [
            {"name": name, "value": str(value)[:1024], "inline": True}
            for name, value in fields
            if value not in (None, "")
        ],
        "footer": {"text": "Hubra · Konto" if de else "Hubra · Account"},
    }
    buttons = []
    if info.get("not_me_url"):
        buttons.append(
            {
                "type": 2,
                "style": 5,
                "label": "Das war ich nicht" if de else "This wasn't me",
                "url": info["not_me_url"],
            }
        )
    if info.get("sessions_url"):
        buttons.append(
            {
                "type": 2,
                "style": 5,
                "label": "Sitzungen prüfen" if de else "Review sessions",
                "url": info["sessions_url"],
            }
        )
    return embed, ([{"type": 1, "components": buttons}] if buttons else [])


def request_embed(user, title: str, text: str, url: str | None = None) -> dict:
    """An answer to one of the account's own requests."""
    embed = {
        "title": title[:256],
        "description": text[:2000],
        "color": COLOR,
        "footer": {"text": "Hubra"},
    }
    if url:
        embed["url"] = url
    return embed


_CASE_STATUS = {
    "open": ("offen", "open"),
    "planned": ("geplant", "planned"),
    "in_progress": ("in Arbeit", "in progress"),
    "done": ("erledigt", "done"),
    "closed": ("geschlossen", "closed"),
}


def support_case_update(
    user, case, *, comment: str | None = None, merged_into=None, url: str = ""
) -> bool:
    """A support case of theirs got an answer, a new status or was merged.
    Called after the commit."""
    de = _de(user)
    if comment:
        title = (
            f"Antwort zu deiner Meldung #{case.id}"
            if de
            else f"Reply to your report #{case.id}"
        )
        text = comment
    elif merged_into is not None:
        title = f"Meldung #{case.id} zusammengeführt" if de else f"Report #{case.id} merged"
        text = (
            f"«{case.title}» geht weiter in #{merged_into.id} {merged_into.title}."
            if de
            else f"“{case.title}” continues in #{merged_into.id} {merged_into.title}."
        )
    else:
        status = _CASE_STATUS.get(case.status, (case.status, case.status))
        title = f"Meldung #{case.id}: {status[0]}" if de else f"Report #{case.id}: {status[1]}"
        text = case.title
    return send(user, "requests", request_embed(user, title, text, url or None), now=True)


def club_request_decided(user, req, url: str = "") -> bool:
    """Their request for a new club was approved or turned down. Called
    after the commit."""
    de = _de(user)
    if req.status == "approved":
        title = "Dein Verein ist bereit" if de else "Your club is ready"
        text = (
            f"Die Anfrage für «{req.name}» ist angenommen."
            if de
            else f"The request for “{req.name}” was approved."
        )
    else:
        title = "Vereinsanfrage abgelehnt" if de else "Club request declined"
        text = (
            f"Die Anfrage für «{req.name}» wurde abgelehnt."
            if de
            else f"The request for “{req.name}” was declined."
        )
        if req.admin_note:
            text += "\n\n" + req.admin_note
    return send(user, "requests", request_embed(user, title, text, url or None), now=True)
