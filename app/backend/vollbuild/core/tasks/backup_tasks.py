"""Celery tasks for database backups."""

from __future__ import annotations

import logging

from vollbuild.core.tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="vollbuild.core.tasks.backup_tasks.create_backup",
)
def create_backup_task(
    self, backup_type: str = "manual", triggered_by: str | None = None
) -> dict:
    """Create a database backup (pg_dump → GPG → S3).

    Args:
        backup_type: 'manual', 'scheduled_daily', 'scheduled_weekly', 'scheduled_monthly'.
        triggered_by: Member name or 'schedule'.
    """
    from vollbuild.core.services.backup import BackupService

    record = BackupService.create_backup(
        backup_type=backup_type, triggered_by=triggered_by
    )
    return {
        "id": record.id,
        "status": record.status,
        "error": record.error_message,
    }


@celery_app.task(
    bind=True,
    name="vollbuild.core.tasks.backup_tasks.verify_backup",
)
def verify_backup_task(self, record_id: int) -> dict:
    """Verify a backup by downloading, decrypting, and checking with pg_restore."""
    from vollbuild.core.services.backup import BackupService

    record = BackupService.verify_backup(record_id)
    return {
        "id": record.id,
        "verified_ok": record.verified_ok,
        "table_count": record.table_count,
        "verify_error": record.verify_error,
    }
