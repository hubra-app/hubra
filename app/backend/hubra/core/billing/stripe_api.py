"""Stripe's HTTP API with the standard library, for billing clubs.

The platform's own Stripe account (``payments.stripe.secret_key``, the key
the payments plugin uses for Connect too) bills the clubs: one customer and
one subscription per club. Same small client as the payments plugin (core
can't import plugins), plus the webhook signature check.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API = "https://api.stripe.com"
VERSION = "2024-06-20"
TIMEOUT = 20


class StripeError(Exception):
    """Stripe refused a call, or could not be reached."""

    def __init__(self, message: str, status: int = 0, code: str | None = None):
        super().__init__(message)
        self.status = status
        self.code = code

    def public_message(self) -> str:
        """What an API answer may say: no text from Stripe or the network
        (logged instead), only whether Stripe answered and its error code."""
        if not self.status:
            return "Stripe could not be reached"
        code = self.code if self.code and self.code.replace("_", "").isalnum() else None
        return f"Stripe refused the call ({code or self.status})"


def _flatten(data: dict, prefix: str = "") -> list[tuple[str, str]]:
    """Stripe's form encoding: a[b][0][c]=x."""
    out: list[tuple[str, str]] = []
    for key, value in data.items():
        name = f"{prefix}[{key}]" if prefix else str(key)
        if value is None:
            continue
        if isinstance(value, dict):
            out += _flatten(value, name)
        elif isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    out += _flatten(item, f"{name}[{i}]")
                else:
                    out.append((f"{name}[{i}]", str(item)))
        elif isinstance(value, bool):
            out.append((name, "true" if value else "false"))
        else:
            out.append((name, str(value)))
    return out


def _send(
    method: str, url: str, headers: dict[str, str], body: bytes | None
) -> tuple[int, bytes]:
    """One HTTP request; tests replace this."""
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def call(
    key: str,
    method: str,
    path: str,
    data: dict | None = None,
    account: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {key}",
        "Stripe-Version": VERSION,
        "User-Agent": "Hubra-Billing/1.0",
    }
    if account:
        headers["Stripe-Account"] = account
    url = API + path
    body = None
    encoded = urllib.parse.urlencode(_flatten(data or {}))
    if method == "GET":
        if encoded:
            url += "?" + encoded
    else:
        body = encoded.encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        headers["Idempotency-Key"] = idempotency_key or secrets.token_hex(16)
    try:
        status, raw = _send(method, url, headers, body)
    except OSError as exc:
        raise StripeError(f"Stripe is not reachable: {exc}") from exc
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        payload = {}
    if status >= 400:
        err = payload.get("error") or {}
        raise StripeError(
            err.get("message") or f"Stripe answered {status}", status, err.get("code")
        )
    return payload


# ── Webhooks ─────────────────────────────────────────────────────────────────

TOLERANCE = 300  # seconds a signed webhook may be old


def verify_signature(
    payload: bytes, header: str, secret: str, now: float | None = None
) -> bool:
    """Stripe's ``Stripe-Signature``: ``t=<time>,v1=<hmac>[,v1=...]``, an
    HMAC-SHA256 of ``<time>.<payload>`` with the endpoint's secret."""
    if not header or not secret:
        return False
    parts: dict[str, list[str]] = {}
    for item in header.split(","):
        key, _, value = item.strip().partition("=")
        parts.setdefault(key, []).append(value)
    try:
        stamp = int(parts.get("t", [""])[0])
    except ValueError:
        return False
    if abs((now or time.time()) - stamp) > TOLERANCE:
        return False
    signed = f"{stamp}.".encode() + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, sig) for sig in parts.get("v1", []))
