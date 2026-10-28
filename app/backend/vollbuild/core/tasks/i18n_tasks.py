"""Celery task for asynchronous missing-key reporting."""

from __future__ import annotations

import logging

from vollbuild.extensions import db
from vollbuild.core.tasks import celery_app

_log = logging.getLogger(__name__)


@celery_app.task(name="vollbuild.core.tasks.i18n_tasks.report_missing_keys_task")
def report_missing_keys_task(locale: str, keys: list[dict]) -> int:
    """Process missing-key reports asynchronously (fire-and-forget).

    Delegates to ``report_missing_keys()`` and commits the transaction.
    """
    from vollbuild.api.i18n.services import report_missing_keys

    try:
        flagged = report_missing_keys(locale, keys)
        db.session.commit()
        return flagged
    except Exception:
        db.session.rollback()
        _log.debug("report_missing_keys_task failed for %s", locale, exc_info=True)
        return 0
