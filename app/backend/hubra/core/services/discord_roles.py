"""Discord Linked Roles: "member of a club on Hubra" on a person's Discord.

A Discord server can give a role only to people whose linked Hubra account
meets a rule its admins pick (Server Settings › Roles › Links), for example
"Club member is true" or "Member since at least 30 days". Discord keeps one
role connection per person and application, so the values are about the
person's Hubra account as a whole, not about one club; the bot's role sync
(groups, functions, tiers) is the per-club tool.

The person allows it once while linking Discord on the SSO account page
(scope ``role_connections.write``). Hubra keeps that token, encrypted with
the platform key, and refreshes the values when the account is linked, every
night, and clears them when it is unlinked.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.error
import urllib.request
from datetime import date

from sqlalchemy import select

from hubra.core.extensions import db
from hubra.core.models.connected_app import ExternalAccount

_log = logging.getLogger(__name__)

API = "https://discord.com/api/v10"
_PURPOSE = "external_accounts.token_encrypted"
_REGISTERED_KEY = "discord:role_metadata"
_local: dict[str, str] = {}

# What a server can make a role depend on. Types: 2 integer ≥, 6 datetime
# (at least so many days ago), 7 boolean equal.
METADATA = [
    {
        "key": "member",
        "name": "Club member",
        "name_localizations": {"de": "Vereinsmitglied"},
        "description": "Active member of a club on Hubra",
        "description_localizations": {"de": "Aktives Mitglied eines Vereins auf Hubra"},
        "type": 7,
    },
    {
        "key": "clubs",
        "name": "Clubs",
        "name_localizations": {"de": "Vereine"},
        "description": "Number of clubs on Hubra",
        "description_localizations": {"de": "Anzahl Vereine auf Hubra"},
        "type": 2,
    },
    {
        "key": "member_since",
        "name": "Member since (days)",
        "name_localizations": {"de": "Mitglied seit (Tage)"},
        "description": "Days since joining the first club",
        "description_localizations": {"de": "Tage seit dem Beitritt zum ersten Verein"},
        "type": 6,
    },
]


class RoleConnectionError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _call(method: str, path: str, auth: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {
        "Authorization": auth,
        "User-Agent": "DiscordBot (https://hubra.club, 2)",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{API}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as resp:  # noqa: S310
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raise RoleConnectionError(f"Discord answered {exc.code}", exc.code) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RoleConnectionError(f"Discord unreachable: {exc}") from exc
    return json.loads(raw) if raw else None


def _settings():
    from hubra.core.services.platform_settings import discord

    return discord()


def available() -> bool:
    app = _settings()
    return bool(app.client_id and app.client_secret and app.bot_token)


# ── The metadata the platform offers ────────────────────────────────────────


def _fingerprint() -> str:
    return hashlib.sha256(json.dumps(METADATA, sort_keys=True).encode()).hexdigest()[
        :16
    ]


def _redis():
    try:
        from hubra.core.redis_client import get_redis_client

        return get_redis_client()
    except Exception:
        return None


def register_metadata(force: bool = False) -> bool:
    """Tell Discord which values servers can use (once per change of
    ``METADATA``). Returns whether it was sent."""
    app = _settings()
    stamp = f"{app.client_id}:{_fingerprint()}"
    r = _redis()
    if not force:
        try:
            known = r.get(_REGISTERED_KEY) if r is not None else None
        except Exception:
            known = None
        if isinstance(known, bytes):
            known = known.decode()
        if (known or _local.get(_REGISTERED_KEY)) == stamp:
            return False
    _call(
        "PUT",
        f"/applications/{app.client_id}/role-connections/metadata",
        f"Bot {app.bot_token}",
        METADATA,
    )
    _local[_REGISTERED_KEY] = stamp
    if r is not None:
        try:
            r.set(_REGISTERED_KEY, stamp)
        except Exception:
            pass
    return True


# ── One person ──────────────────────────────────────────────────────────────


def values_for(user_id: int) -> dict:
    """The person's values: an active member anywhere, how many clubs, and
    since when."""
    from hubra.core.services.account import memberships

    joined: list[date] = []
    count = 0
    for _tenant, member in memberships(user_id):
        if member.is_blocked or member.status == "inactive":
            continue
        count += 1
        if member.joined:
            joined.append(member.joined)
    values: dict = {"member": 1 if count else 0, "clubs": count}
    if joined:
        values["member_since"] = min(joined).isoformat()
    return values


def read_token(acc: ExternalAccount) -> dict | None:
    if not acc.token_encrypted:
        return None
    from hubra.core.crypto import PLATFORM, InvalidToken, decrypt_code

    try:
        return json.loads(decrypt_code(acc.token_encrypted, _PURPOSE, PLATFORM))
    except (InvalidToken, ValueError):
        _log.warning("external account %s: token can't be read", acc.id)
        return None


def store_token(acc: ExternalAccount, token: dict | None) -> None:
    from hubra.core.crypto import PLATFORM, encrypt_code

    acc.token_encrypted = (
        encrypt_code(json.dumps(token), _PURPOSE, PLATFORM) if token else None
    )


def _access(acc: ExternalAccount) -> str | None:
    """A valid access token, refreshed when it is about to run out; None
    (and the token forgotten) when Discord no longer accepts it."""
    from hubra.core.identity import IdentityError, provider

    token = read_token(acc)
    if not token:
        return None
    if int(token.get("expires_at") or 0) - 60 > time.time():
        return token["access"]
    if not token.get("refresh"):
        store_token(acc, None)
        return None
    try:
        token = provider("discord").refresh(token["refresh"])
    except IdentityError as exc:
        _log.info("discord: refresh for account %s failed: %s", acc.id, exc)
        store_token(acc, None)  # revoked or expired: they link again
        return None
    store_token(acc, token)
    return token["access"]


def push(acc: ExternalAccount) -> bool:
    """Send the person's current values to Discord. Returns whether it was
    sent (False: no token, or Discord dropped it). Caller commits."""
    if acc.provider != "discord" or not available():
        return False
    access = _access(acc)
    if access is None:
        return False
    register_metadata()
    body = {"platform_name": "Hubra", "metadata": values_for(acc.user_id)}
    try:
        _call(
            "PUT",
            f"/users/@me/applications/{_settings().client_id}/role-connection",
            f"Bearer {access}",
            body,
        )
    except RoleConnectionError as exc:
        if exc.status == 401:
            store_token(acc, None)
            return False
        raise
    return True


def clear(token: dict | None) -> None:
    """Empty the role connection and revoke the token (on unlink)."""
    if not token or not available():
        return
    from hubra.core.identity import provider

    try:
        if int(token.get("expires_at") or 0) > time.time():
            _call(
                "PUT",
                f"/users/@me/applications/{_settings().client_id}/role-connection",
                f"Bearer {token['access']}",
                {"platform_name": "Hubra", "metadata": {}},
            )
    except RoleConnectionError as exc:
        _log.info("discord: could not clear a role connection: %s", exc)
    for key in ("refresh", "access"):
        if token.get(key):
            provider("discord").revoke(token[key])


def push_all() -> int:
    """Every account with a kept token (nightly). Returns how many were sent."""
    if not available():
        return 0
    sent = 0
    ids = db.session.scalars(
        select(ExternalAccount.id).where(
            ExternalAccount.provider == "discord",
            ExternalAccount.token_encrypted.is_not(None),
        )
    ).all()
    for acc_id in ids:
        acc = db.session.get(ExternalAccount, acc_id)
        if acc is None:
            continue
        try:
            sent += push(acc)
        except RoleConnectionError as exc:
            _log.info("discord: role connection for account %s: %s", acc_id, exc)
        db.session.commit()
    return sent
