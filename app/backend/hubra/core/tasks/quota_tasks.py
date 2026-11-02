"""Hourly check of every club against its limits (see core/services/quotas.py)."""

from __future__ import annotations

from hubra.core.tasks import celery_app


@celery_app.task(name="hubra.core.tasks.quota_tasks.check_quotas")
def check_quotas() -> dict:
    """Warn club owners and the platform when a club nears or reaches a limit."""
    from hubra.core.services import quotas

    return quotas.check_all()
