"""Outside accounts a person links to their Hubra account (SSO account page).

The outside account's id and name are kept, to recognise the person when
the service talks to Hubra (a click on a Discord button). For Discord, the
token is also kept (encrypted) when the person allowed Linked Roles, so
Hubra can keep their role connection up to date (see
``hubra.core.services.discord_roles``); otherwise it is revoked right away.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


_log = logging.getLogger(__name__)


class IdentityError(Exception):
    pass


@dataclass
class Identity:
    external_id: str
    username: str
    # Kept only when the service needs it later: {"access", "refresh",
    # "expires_at" (Unix seconds), "scope"}.
    token: dict | None = None


class DiscordIdentity:
    code = "discord"
    name = "Discord"
    api = "https://discord.com/api/v10"

    def _client(self) -> tuple[str, str]:
        from hubra.core.services.platform_settings import discord

        app = discord()
        return app.client_id, app.client_secret

    def available(self) -> bool:
        return all(self._client())

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        client_id, _ = self._client()
        query = urllib.parse.urlencode(
            {
                "client_id": client_id,
                "response_type": "code",
                "redirect_uri": redirect_uri,
                # Who you are and your Linked Roles connection, nothing
                # else: no email, no servers.
                "scope": "identify role_connections.write",
                "state": state,
                "prompt": "consent",
            }
        )
        return f"https://discord.com/oauth2/authorize?{query}"

    def _post_form(self, path: str, data: dict) -> dict:
        request = urllib.request.Request(
            f"{self.api}{path}",
            data=urllib.parse.urlencode(data).encode(),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "hubra",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as resp:  # noqa: S310
            body = resp.read()
        return json.loads(body) if body else {}

    def identify(self, code: str, redirect_uri: str) -> Identity:
        client_id, client_secret = self._client()
        try:
            token = self._post_form(
                "/oauth2/token",
                {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            access = token.get("access_token")
            if not access:
                raise IdentityError("Discord sent no token")
            request = urllib.request.Request(
                f"{self.api}/users/@me",
                headers={"Authorization": f"Bearer {access}", "User-Agent": "hubra"},
            )
            with urllib.request.urlopen(request, timeout=10) as resp:  # noqa: S310
                me = json.loads(resp.read())
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise IdentityError(f"Discord sign-in failed: {exc}") from exc
        if not me.get("id"):
            raise IdentityError("Discord sent no user")
        name = me.get("global_name") or me.get("username") or ""
        kept = None
        if "role_connections.write" in str(token.get("scope", "")).split():
            import time

            kept = {
                "access": access,
                "refresh": token.get("refresh_token") or "",
                "expires_at": int(time.time()) + int(token.get("expires_in") or 0),
                "scope": token.get("scope", ""),
            }
        else:
            self.revoke(access)
        return Identity(external_id=str(me["id"]), username=str(name)[:200], token=kept)

    def revoke(self, token: str) -> None:
        """Make a token invalid at Discord (best effort)."""
        client_id, client_secret = self._client()
        try:
            self._post_form(
                "/oauth2/token/revoke",
                {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "token": token,
                },
            )
        except Exception as exc:  # the link works without it
            _log.info("discord: could not revoke a token: %s", exc)

    def refresh(self, refresh_token: str) -> dict:
        """A new access token for a kept refresh token."""
        import time

        client_id, client_secret = self._client()
        try:
            token = self._post_form(
                "/oauth2/token",
                {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
            )
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise IdentityError(f"Discord token refresh failed: {exc}") from exc
        if not token.get("access_token"):
            raise IdentityError("Discord sent no token")
        return {
            "access": token["access_token"],
            "refresh": token.get("refresh_token") or refresh_token,
            "expires_at": int(time.time()) + int(token.get("expires_in") or 0),
            "scope": token.get("scope", ""),
        }


PROVIDERS = {p.code: p for p in (DiscordIdentity(),)}


def provider(code: str):
    return PROVIDERS.get(code)
