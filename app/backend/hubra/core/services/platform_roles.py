"""Roles on the platform's own Discord server that follow Hubra.

With the platform setting ``discord.platform_roles`` on, the bot keeps these
roles on the platform server (the server of the platform log channel) for
everyone who linked their Discord account in SSO:

* **Plattform-Admin**: platform staff with two-factor, the same people the
  platform buttons and commands accept (``platform_bot.admin_for``).
* **Vereinsinhaber**: owner of at least one active club.
* **Vereinsadmin**: admin (not owner) of at least one active club.
* **Vereinsmitglied**: member of at least one active club.

The bot makes these roles itself, with no permissions and not mentionable;
what a role may see is set on Discord. It only ever gives or takes these
roles, never one a person made, and never touches people who did not link
Discord. Disabled accounts and people who unlink lose them. Turning the
setting off deletes the roles again.

Runs from ``platform_bot_tasks.tick`` every few minutes (only people whose
roles should change cost a call to Discord), right after someone links
Discord, and in full once a day.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import select

from hubra.core.extensions import db

_log = logging.getLogger(__name__)

ROLES = (
    ("platform_admin", "Plattform-Admin"),
    ("club_owner", "Vereinsinhaber"),
    ("club_admin", "Vereinsadmin"),
    ("club_member", "Vereinsmitglied"),
)
SETTING = "discord.platform_roles"
SYNC_EVERY = 10 * 60
_IDS_KEY = "platform_bot:roles:ids"
_APPLIED_KEY = "platform_bot:roles:applied"
REASON = "Hubra: platform roles"


def enabled() -> bool:
    from hubra.core.services import platform_settings

    return platform_settings.get(SETTING) == "on"


def _bot(method: str, path: str, body=None):
    from hubra.core.services import platform_bot

    return platform_bot._bot(method, path, body)


# ── What a person should have ─────────────────────────────────────────────────


def _active_member(member) -> bool:
    return (
        member.archived_at is None
        and getattr(member, "deleted_at", None) is None
        and not getattr(member, "is_blocked", False)
        and getattr(member, "status", "active") != "inactive"
    )


def wanted(user) -> set[str]:
    """The role keys *user* should have (see ``ROLES``)."""
    from hubra.api.auth import mfa
    from hubra.api.permissions import held_roles
    from hubra.core.services import account

    if user is None or user.is_disabled:
        return set()
    out: set[str] = set()
    try:
        if mfa.is_staff(user) and mfa.enabled(user):
            out.add("platform_admin")
    except Exception:  # noqa: BLE001
        _log.warning("platform roles: staff check failed", exc_info=True)
    for _tenant, member in account.memberships(user.id):
        if not _active_member(member):
            continue
        out.add("club_member")
        roles = held_roles(member)
        if any(r.is_owner for r in roles):
            out.add("club_owner")
        elif any(r.is_admin for r in roles):
            out.add("club_admin")
    return out


# ── The roles on the server ───────────────────────────────────────────────────


def _stored_ids() -> dict[str, str]:
    from hubra.core.services import platform_bot

    try:
        ids = json.loads(platform_bot._get(_IDS_KEY) or "{}")
    except ValueError:
        return {}
    return {k: str(v) for k, v in ids.items() if k in dict(ROLES)}


def _ours(role: dict) -> bool:
    """A role that looks like one the bot made: no permissions, not managed
    by an integration. Only such a role is taken over by name."""
    return str(role.get("permissions") or "0") == "0" and not role.get("managed")


def ensure_roles(guild: str) -> dict[str, str]:
    """Make the roles that are missing. Returns {key: role id}."""
    from hubra.core.services import platform_bot

    server = {r["id"]: r for r in _bot("GET", f"/guilds/{guild}/roles") or []}
    ids = {k: v for k, v in _stored_ids().items() if v in server}
    for key, name in ROLES:
        if key in ids:
            continue
        found = next(
            (r for r in server.values() if r.get("name") == name and _ours(r)), None
        )
        if found is None:
            found = _bot(
                "POST",
                f"/guilds/{guild}/roles",
                {
                    "name": name,
                    "permissions": "0",
                    "mentionable": False,
                    "hoist": False,
                },
            )
        ids[key] = str(found["id"])
    platform_bot._set(_IDS_KEY, json.dumps(ids))
    return ids


def remove_roles(guild: str) -> int:
    """Delete the bot's roles (setting turned off). Returns how many."""
    from hubra.core.services import platform_bot

    done = 0
    for role_id in _stored_ids().values():
        try:
            _bot("DELETE", f"/guilds/{guild}/roles/{role_id}")
            done += 1
        except platform_bot.BotError as exc:
            if exc.status != 404:
                raise
    platform_bot._delete(_IDS_KEY)
    platform_bot._delete(_APPLIED_KEY)
    return done


# ── Giving and taking ─────────────────────────────────────────────────────────


def _applied() -> dict[str, str]:
    from hubra.core.services import platform_bot

    client = platform_bot._redis()
    if client is None:
        return {}
    try:
        raw = client.hgetall(_APPLIED_KEY) or {}
    except Exception:  # noqa: BLE001
        return {}
    return {
        (k.decode() if isinstance(k, bytes) else str(k)): (
            v.decode() if isinstance(v, bytes) else str(v)
        )
        for k, v in raw.items()
    }


def _remember(discord_id: str, keys: set[str] | None) -> None:
    from hubra.core.services import platform_bot

    client = platform_bot._redis()
    if client is None:
        return
    try:
        if keys is None:
            client.hdel(_APPLIED_KEY, discord_id)
        else:
            client.hset(_APPLIED_KEY, discord_id, ",".join(sorted(keys)))
    except Exception:  # noqa: BLE001
        pass


def apply(guild: str, ids: dict[str, str], discord_id: str, keys: set[str]) -> bool:
    """Give *discord_id* exactly the roles *keys* among the bot's roles.
    False when the person is not on the server."""
    from hubra.core.services import platform_bot

    try:
        member = _bot("GET", f"/guilds/{guild}/members/{discord_id}") or {}
    except platform_bot.BotError as exc:
        if exc.status == 404:
            return False
        raise
    ours = set(ids.values())
    have = set(member.get("roles") or []) & ours
    want = {ids[k] for k in keys if k in ids}
    base = f"/guilds/{guild}/members/{discord_id}/roles"
    for role_id in sorted(want - have):
        _bot("PUT", f"{base}/{role_id}")
    for role_id in sorted(have - want):
        _bot("DELETE", f"{base}/{role_id}")
    return True


def sync(user_ids: list[int] | None = None, force: bool = False) -> int:
    """Bring the roles of linked people up to date (all, or *user_ids*).
    Returns how many people were checked on Discord."""
    from hubra.core.models.connected_app import ExternalAccount
    from hubra.core.models.user import User
    from hubra.core.services import platform_bot

    guild = platform_bot.guild_id()
    if not guild:
        return 0
    if not enabled():
        if _stored_ids():
            remove_roles(guild)
        return 0
    ids = ensure_roles(guild)
    query = select(ExternalAccount.user_id, ExternalAccount.external_id).where(
        ExternalAccount.provider == "discord"
    )
    if user_ids is not None:
        query = query.where(ExternalAccount.user_id.in_(user_ids))
    linked = db.session.execute(query).all()
    applied = _applied()
    checked = 0
    for user_id, discord_id in linked:
        discord_id = str(discord_id)
        keys = wanted(db.session.get(User, user_id))
        if not force and applied.get(discord_id) == ",".join(sorted(keys)):
            continue
        checked += 1
        if apply(guild, ids, discord_id, keys):
            _remember(discord_id, keys)
        else:
            _remember(discord_id, None)  # not on the server (yet)
    if user_ids is None:
        # Unlinked since the last run: take the roles away.
        still = {str(d) for _, d in linked}
        for discord_id in set(applied) - still:
            checked += 1
            apply(guild, ids, discord_id, set())
            _remember(discord_id, None)
    return checked


def due() -> bool:
    """Once per ``SYNC_EVERY``, even with several workers."""
    from hubra.core.services import platform_bot

    return platform_bot._set("platform_bot:roles:due", "1", ex=SYNC_EVERY, nx=True)


def later(user_id: int) -> None:
    """Sync one person after the commit (they just linked Discord)."""
    try:
        from hubra.core.tasks.after_commit import delay_after_commit
        from hubra.core.tasks.platform_bot_tasks import sync_roles

        delay_after_commit(sync_roles, user_id)
    except Exception:  # noqa: BLE001
        _log.warning("platform roles: sync not queued", exc_info=True)


def joined(guild: str, discord_id: str) -> bool:
    """Someone joined a server (from the Discord plugin's gateway). On the
    platform server, give them their roles now. True when handled."""
    from hubra.core.models.connected_app import ExternalAccount
    from hubra.core.services import platform_bot

    platform = platform_bot.guild_id()
    if not platform or str(guild) != platform or not enabled():
        return False
    user_id = db.session.scalar(
        select(ExternalAccount.user_id).where(
            ExternalAccount.provider == "discord",
            ExternalAccount.external_id == str(discord_id),
        )
    )
    if user_id is not None:
        sync([user_id], force=True)
    return True
