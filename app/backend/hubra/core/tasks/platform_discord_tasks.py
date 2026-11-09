"""Celery task that posts a platform audit entry to the platform Discord log.

See ``services.platform_discord``.  Never raises: a failed post is logged,
not retried, and must not turn into a failed-task alert about itself.
"""

from __future__ import annotations

import logging

from hubra.core.tasks import celery_app

_log = logging.getLogger(__name__)


@celery_app.task(
    name="hubra.core.tasks.platform_discord_tasks.post_platform_audit_entry",
    ignore_result=True,
)
def post_platform_audit_entry(entry_id: int) -> bool:
    """Discord first, then the admin mails (``notify.mail_events``); a
    failure in one does not stop the other."""
    from hubra.core.extensions import db
    from hubra.core.models.tenant import GlobalAuditEntry
    from hubra.core.services import platform_discord, platform_monitor

    posted = False
    try:
        posted = platform_discord.post_audit_entry(int(entry_id))
    except Exception as exc:
        _log.warning("platform Discord log: entry %s not posted: %s", entry_id, exc)
    try:
        entry = db.session.get(GlobalAuditEntry, int(entry_id))
        if entry is not None:
            platform_monitor.deliver_audit_mail(entry)
    except Exception as exc:
        _log.warning("platform audit mail: entry %s not sent: %s", entry_id, exc)
    return posted


@celery_app.task(name="hubra.core.tasks.platform_discord_tasks.check_discord_bot")
def check_discord_bot_task() -> dict:
    """Ask Discord about the bot in the background (every 4 minutes, under
    discord_status.CHECK_TTL), so manage's Discord page reads the stored
    check instead of waiting seconds for Discord."""
    from hubra.core.services import discord_status, platform_settings

    if not platform_settings.discord().bot_token:
        return {"skipped": "no bot token"}
    result = discord_status.run_check()
    return {"botOk": result.get("botOk")}
