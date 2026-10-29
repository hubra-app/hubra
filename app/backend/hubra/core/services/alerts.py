"""Discord webhook alerting for infrastructure monitoring.

Uses urllib.request (no new dependencies). Configurable via DISCORD_WEBHOOK_URL.
"""

import json
import logging
import os
import urllib.request
from typing import Any

_log = logging.getLogger(__name__)

# Alert color constants (Discord embed colors)
COLOR_RED = 0xE74C3C  # Critical / error
COLOR_ORANGE = 0xF39C12  # Warning
COLOR_GREEN = 0x2ECC71  # Resolved / OK


def _get_webhook_url() -> str:
    """Return the Discord webhook URL from config or environment."""
    try:
        from flask import current_app

        return current_app.config.get("DISCORD_WEBHOOK_URL", "")
    except RuntimeError:
        return os.environ.get("DISCORD_WEBHOOK_URL", "")


def send_alert(
    title: str,
    description: str,
    color: int = COLOR_RED,
    fields: list[dict[str, Any]] | None = None,
) -> bool:
    """Send a Discord embed alert via webhook.

    Returns True if the alert was sent successfully, False otherwise.
    Never raises — alerting failures are silently logged.
    """
    url = _get_webhook_url()
    if not url:
        _log.debug("DISCORD_WEBHOOK_URL not configured, skipping alert")
        return False

    embed: dict[str, Any] = {
        "title": title,
        "description": description,
        "color": color,
    }

    if fields:
        embed["fields"] = [
            {"name": f["name"], "value": f["value"], "inline": f.get("inline", False)}
            for f in fields
        ]

    payload = json.dumps({"embeds": [embed]}).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            # Discord returns 204 No Content on success
            return resp.status in (200, 204)
    except Exception:
        _log.warning("Failed to send Discord alert: %s", title, exc_info=True)
        return False


def alert_error(
    title: str,
    description: str,
    fields: list[dict[str, Any]] | None = None,
) -> bool:
    """Send a red (error) alert."""
    return send_alert(title, description, color=COLOR_RED, fields=fields)


def alert_warning(
    title: str,
    description: str,
    fields: list[dict[str, Any]] | None = None,
) -> bool:
    """Send an orange (warning) alert."""
    return send_alert(title, description, color=COLOR_ORANGE, fields=fields)


def alert_resolved(
    title: str,
    description: str,
    fields: list[dict[str, Any]] | None = None,
) -> bool:
    """Send a green (resolved) alert."""
    return send_alert(title, description, color=COLOR_GREEN, fields=fields)
