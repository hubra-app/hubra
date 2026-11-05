"""Calls to the Hubra API with the caller's own token.

The connector has no credentials and no database of its own. Every call
carries the bearer token the MCP client sent, goes only to the configured
Hubra API (never to a URL a tool argument names), never follows a redirect,
and says it comes from an AI assistant so clubs that haven't allowed that
refuse it (``X-Hubra-Client: mcp``).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

import httpx
from mcp.server.mcpserver.exceptions import ToolError

from hubra_mcp import __version__

# Same shape as the backend's tokens (hubra/core/auth/api_tokens.py): API
# tokens someone pasted, and OAuth access tokens (oam: a club, oap: the
# platform) Claude got by signing in (docs/oauth.md).
TOKEN_RE = re.compile(r"^hbr_(pat|club|plat|oam|oap)_[A-Za-z0-9]{12}_[A-Za-z0-9]{43}$")
KIND_BY_PREFIX = {
    "pat": "member",
    "club": "club",
    "plat": "platform",
    "oam": "member",
    "oap": "platform",
}

# Paths a tool may read: the token's own side of the API, plain segments.
_PATH_RE = re.compile(r"^/api/v1/(app|platform)(/[A-Za-z0-9_\-.]+)*/?$")

MAX_CHARS = 60_000
TIMEOUT = httpx.Timeout(30.0, connect=5.0)


class HubraError(ToolError):
    """Something the model should read as a plain answer, not a crash."""


@dataclass(frozen=True)
class Settings:
    api_url: str
    platform_api_url: str

    @classmethod
    def from_env(cls) -> Settings:
        api = os.environ.get("HUBRA_API_URL", "http://localhost:5000").rstrip("/")
        platform = os.environ.get("HUBRA_PLATFORM_API_URL", "").rstrip("/") or api
        for url in (api, platform):
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"HUBRA_API_URL must be http(s): {url!r}")
        return cls(api_url=api, platform_api_url=platform)


def token_kind(token: str | None) -> str | None:
    """``member``, ``club`` or ``platform`` for a well-formed token, else None."""
    if not token:
        return None
    match = TOKEN_RE.match(token)
    return KIND_BY_PREFIX[match.group(1)] if match else None


def is_oauth(token: str | None) -> bool:
    return bool(token) and token.startswith(("hbr_oam_", "hbr_oap_"))  # type: ignore[union-attr]


def bearer(headers) -> str | None:
    """The hbr_ token from an Authorization header mapping, or None."""
    if headers is None:
        return None
    value = headers.get("authorization") or headers.get("Authorization") or ""
    if not value.startswith("Bearer "):
        return None
    token = value[len("Bearer ") :].strip()
    return token if token_kind(token) else None


def check_path(path: str, kind: str) -> str:
    """A read path on the token's own side of the API, or HubraError."""
    if not isinstance(path, str) or not _PATH_RE.match(path) or ".." in path:
        raise HubraError(
            "Path must look like /api/v1/app/events/ or /api/v1/platform/health"
        )
    side = path.split("/")[3]
    if (side == "platform") != (kind == "platform"):
        want = "/api/v1/platform/…" if kind == "platform" else "/api/v1/app/…"
        raise HubraError(f"This token reads {want} only")
    return path


def _clean_params(params: dict[str, Any] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in (params or {}).items():
        if value is None or value == "":
            continue
        if not isinstance(key, str) or not re.match(r"^[A-Za-z_][A-Za-z0-9_]{0,40}$", key):
            raise HubraError(f"Bad query parameter name: {key!r}")
        if isinstance(value, bool):
            value = "true" if value else "false"
        if not isinstance(value, (str, int, float)):
            raise HubraError(f"Query parameter {key} must be text or a number")
        out[key] = str(value)[:200]
    return out


def shorten(text: str, limit: int = MAX_CHARS) -> str:
    if len(text) <= limit:
        return text
    return (
        text[:limit]
        + f"\n… cut after {limit} of {len(text)} characters; ask for a smaller page"
        " (page/pageSize) or a narrower filter."
    )


class Hubra:
    """One API client for the whole process; the token comes per call."""

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self._client = httpx.AsyncClient(
            timeout=TIMEOUT,
            follow_redirects=False,
            transport=transport,
            headers={
                "User-Agent": f"hubra-mcp/{__version__}",
                "Accept": "application/json",
                "X-Hubra-Client": "mcp",
            },
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def check(self, token: str) -> int:
        """Ask Hubra whether *token* still works ("which token is this?"):
        the HTTP status, or 503 when Hubra can't be reached."""
        kind = token_kind(token)
        path = "/api/v1/platform/api-tokens/self" if kind == "platform" else "/api/v1/app/api-tokens/self"
        base = self.settings.platform_api_url if kind == "platform" else self.settings.api_url
        try:
            resp = await self._client.get(base + path, headers={"Authorization": f"Bearer {token}"})
        except httpx.HTTPError:
            return 503
        return resp.status_code

    async def resource_metadata(self) -> dict | None:
        """The connector's OAuth resource metadata (RFC 9728), from Hubra's
        platform settings; None while it isn't set up."""
        try:
            resp = await self._client.get(self.settings.api_url + "/api/v1/global/oauth/resource")
        except httpx.HTTPError:
            return None
        if resp.status_code != 200:
            return None
        try:
            body = resp.json()
        except ValueError:
            return None
        return body if isinstance(body, dict) and body.get("resource") else None

    async def get(
        self,
        token: str,
        path: str,
        params: dict[str, Any] | None = None,
        client_ip: str | None = None,
    ) -> Any:
        kind = token_kind(token)
        if kind is None:
            raise HubraError("No valid Hubra API token on this connection")
        check_path(path, kind)
        base = self.settings.platform_api_url if kind == "platform" else self.settings.api_url
        headers = {"Authorization": f"Bearer {token}"}
        if client_ip:
            # The person's address (server._forwarded_for). Hubra reads it
            # with its proxy setting (wsgi.py) when the connector calls a
            # backend directly; through the ingress it sees the connector.
            headers["X-Forwarded-For"] = client_ip
        try:
            resp = await self._client.get(base + path, params=_clean_params(params), headers=headers)
        except httpx.HTTPError as exc:
            raise HubraError(f"Hubra API not reachable ({type(exc).__name__})") from None
        if resp.is_redirect:
            raise HubraError(f"Hubra answered with a redirect ({resp.status_code})")
        try:
            body = resp.json()
        except ValueError:
            body = None
        if resp.status_code >= 400:
            if isinstance(body, dict):
                code = body.get("error") or body.get("code") or ""
                message = body.get("message") or ""
                raise HubraError(f"Hubra answered {resp.status_code} {code}: {message}".strip())
            raise HubraError(f"Hubra answered {resp.status_code}")
        if body is None:
            raise HubraError("Hubra answered something that isn't JSON")
        return body


def as_text(body: Any) -> str:
    return shorten(json.dumps(body, ensure_ascii=False, separators=(",", ":"), default=str))
