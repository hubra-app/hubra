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
    from hubra.core.services import platform_discord

    try:
        return platform_discord.post_audit_entry(int(entry_id))
    except Exception as exc:
        _log.warning("platform Discord log: entry %s not posted: %s", entry_id, exc)
        return False
