"""System alerts for infrastructure monitoring.

Alerts are posted by the Hubra bot to the platform Discord log channel
(manage › Discord › Setup, category ``alerts``); see
``services.platform_discord``.  Nothing is sent while that is not set up.
"""

import logging
from typing import Any

_log = logging.getLogger(__name__)

# Alert color constants (Discord embed colors)
COLOR_RED = 0xE74C3C  # Critical / error
COLOR_ORANGE = 0xF39C12  # Warning
COLOR_GREEN = 0x2ECC71  # Resolved / OK


def send_alert(
    title: str,
    description: str,
    color: int = COLOR_RED,
    fields: list[dict[str, Any]] | None = None,
    *,
    staff: bool = True,
    alert_type: str = "system",
) -> bool:
    """Post an alert embed to the platform Discord log.

    Returns True if the alert was sent successfully, False otherwise.
    Never raises — alerting failures are silently logged.

    The alert also goes to the platform event log and, by mail, to platform
    staff who want system alerts (``platform_monitor.system_alert``);
    ``staff=False`` when platform_monitor itself posts here.
    """
    if staff:
        _to_platform_staff(title, description, fields, color)
        if not _discord_on():
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

    from hubra.core.services import platform_discord

    return platform_discord.post_alert(embed, alert_type)


def _to_platform_staff(title, description, fields, color) -> None:
    try:
        from flask import has_app_context

        if not has_app_context():
            return
        from hubra.core.services import platform_monitor

        platform_monitor.system_alert(title, description, fields, color)
    except Exception:
        _log.warning("Failed to log platform alert: %s", title, exc_info=True)


def _discord_on() -> bool:
    """Whether system alerts go to Discord now (alert switches, maintenance)."""
    try:
        from flask import has_app_context

        if not has_app_context():
            return True
        from hubra.core.services import platform_monitor

        return platform_monitor.channels("system")["discord"]
    except Exception:  # noqa: BLE001
        return True


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
