"""POST /auth/redirect-loop: a portal stopped an endless redirect.

The club app, SSO and manage send each other back and forth when a session
is missing or not good enough.  Every automatic redirect is noted in a
short-lived cookie (packages/api-client/src/redirectGuard.ts); when too many
pile up in a few seconds the page stops, shows an error page and reports the
chain here.  The report goes to the platform event log (manage › Diagnostics
› Event log, category ``system``, kind ``redirect_loop``) and the app log,
with the sign-in session it happened in, so loops can be traced per session.

Anyone may report (a loop often starts with a broken session), so the input
is cut down hard: at most a few hops, host + path only, short reason codes.
Nothing from the query or hash is kept, so no token ends up in the log.
"""

from __future__ import annotations

import logging
import re

from flask import Blueprint, jsonify, request

from hubra.api.auth.services import _extract_browser_family
from hubra.core.extensions import limiter
from hubra.core.services import platform_monitor

_log = logging.getLogger(__name__)

redirect_loop_bp = Blueprint("redirect_loop_bp", __name__)

MAX_HOPS = 12
_PART = re.compile(r"[^A-Za-z0-9._:/@%+~-]")
_WHY = re.compile(r"[^a-z0-9-]")


def _clean_place(value: object) -> str:
    """host + path, without query or hash, only harmless characters."""
    text = str(value or "")[:200]
    text = text.split("?", 1)[0].split("#", 1)[0]
    return _PART.sub("", text)[:120]


def _clean_why(value: object) -> str:
    return _WHY.sub("", str(value or "").lower())[:40] or "unknown"


def _clean_hops(raw: object) -> list[dict]:
    if not isinstance(raw, list):
        return []
    hops = []
    for item in raw[-MAX_HOPS:]:
        if not isinstance(item, dict):
            continue
        try:
            ms = max(0, min(int(item.get("ms") or 0), 3_600_000))
        except (TypeError, ValueError):
            ms = 0
        hops.append(
            {
                "ms": ms,
                "from": _clean_place(item.get("from")),
                "to": _clean_place(item.get("to")),
                "why": _clean_why(item.get("why")),
            }
        )
    return hops


def _session_claims() -> dict:
    """Who it happened to, when the cookies still say so.  Never raises: a
    loop often comes from a session the API no longer accepts."""
    try:
        from flask_jwt_extended import get_jwt, verify_jwt_in_request

        verify_jwt_in_request(optional=True)
        claims = get_jwt() or {}
    except Exception:
        claims = {}
    if not claims:
        try:
            from hubra.api.auth import account_token

            claims = account_token.read_claims() or {}
        except Exception:
            claims = {}
    keep = {}
    for key in ("user_id", "sid", "account_sid", "tenant_slug"):
        if claims.get(key) is not None:
            keep[key] = claims[key]
    return keep


def _chain(hops: list[dict]) -> str:
    if not hops:
        return ""
    parts = [hops[0]["from"]]
    parts += [f"{h['to']} ({h['why']})" for h in hops]
    return " → ".join(parts)


@redirect_loop_bp.post("/redirect-loop")
@limiter.limit("6 per minute")
def report_redirect_loop():
    body = request.get_json(silent=True) or {}
    hops = _clean_hops(body.get("hops"))
    if not hops:
        return jsonify(error="BAD_REQUEST", message="No hops"), 400
    page = _clean_place(body.get("page"))
    session = _session_claims()
    reasons = sorted({h["why"] for h in hops})
    chain = _chain(hops)

    _log.warning(
        "redirect_loop user_id=%s account_sid=%s sid=%s club=%s hops=%d reasons=%s chain=%s",
        session.get("user_id"),
        session.get("account_sid"),
        session.get("sid"),
        session.get("tenant_slug"),
        len(hops),
        ",".join(reasons),
        chain,
    )
    platform_monitor.record(
        "system",
        "redirect_loop",
        f"Redirect loop stopped on {page or 'a page'} after {len(hops)} redirects "
        f"({', '.join(reasons)})",
        level="warning",
        details={
            "page": page,
            "hops": hops,
            "session": session,
            # The browser family only, not the whole User-Agent.
            "browser": _extract_browser_family(request.headers),
        },
    )
    return jsonify(ok=True), 202
