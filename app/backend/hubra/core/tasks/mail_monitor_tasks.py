"""Periodic relay checks, alert mails to platform staff and event-log cleanup
(see core/services/platform_monitor.py)."""

from __future__ import annotations

import logging

from hubra.core.tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="hubra.core.tasks.mail_monitor_tasks.check_mail_relays")
def check_mail_relays() -> dict:
    """Log in to the main and the fallback relay; alert when one goes down."""
    from hubra.core.services import platform_monitor

    out = {}
    for which in platform_monitor.RELAYS:
        result = platform_monitor.run_check(which, scheduled=True)
        out[which] = result.get("ok")
    return out


@celery_app.task(name="hubra.core.tasks.mail_monitor_tasks.send_platform_alert")
def send_platform_alert(
    alert_type: str, subject: str, lines: list, level: str, link: str | None = None
) -> int:
    """Mail one alert to platform staff.  Never retried: a failed alert mail
    is in the event log, and retrying through a broken relay helps nobody."""
    from hubra.core.services import platform_monitor

    try:
        return platform_monitor.deliver_alert(
            alert_type, subject, list(lines), level, link=link
        )
    except Exception:
        logger.warning("platform_alert_delivery_failed", exc_info=True)
        return 0


@celery_app.task(name="hubra.core.tasks.mail_monitor_tasks.prune_platform_events")
def prune_platform_events() -> int:
    from hubra.core.services import platform_monitor

    return platform_monitor.prune()
