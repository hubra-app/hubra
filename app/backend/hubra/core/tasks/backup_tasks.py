"""Celery tasks for backups: the global one, per club, and club restores."""

from __future__ import annotations

import logging

from hubra.core.tasks import celery_app

logger = logging.getLogger(__name__)


def _unseal(sealed_key: str | None) -> str | None:
    if not sealed_key:
        return None
    from hubra.core.crypto import InvalidToken, unseal

    try:
        return unseal(sealed_key)
    except InvalidToken:
        raise RuntimeError(
            "The private key for this task expired; start it again"
        ) from None


@celery_app.task(
    bind=True,
    name="hubra.core.tasks.backup_tasks.create_backup",
)
def create_backup_task(
    self,
    backup_type: str = "manual",
    triggered_by: str | None = None,
    tenant_id: int | None = None,
) -> dict:
    """Back up one schema (pg_dump → GPG → S3).

    Args:
        backup_type: 'manual', 'scheduled_daily', 'scheduled_weekly', 'scheduled_monthly'.
        triggered_by: Member name or 'schedule'.
        tenant_id: The club to back up; None backs up the global public schema.
    """
    from hubra.core.services.backup import BackupService

    record = BackupService.create_backup(
        backup_type=backup_type, triggered_by=triggered_by, tenant_id=tenant_id
    )
    return {
        "id": record.id,
        "status": record.status,
        "error": record.error_message,
    }


@celery_app.task(
    bind=True,
    name="hubra.core.tasks.backup_tasks.verify_backup",
)
def verify_backup_task(self, record_id: int, sealed_key: str | None = None) -> dict:
    """Verify a backup by downloading, decrypting, and checking with pg_restore.

    *sealed_key*: the backup private key, sealed by the request
    (``hubra.core.crypto.seal``).
    """
    from hubra.core.services.backup import BackupService

    record = BackupService.verify_backup(record_id, _unseal(sealed_key))
    return {
        "id": record.id,
        "verified_ok": record.verified_ok,
        "table_count": record.table_count,
        "verify_error": record.verify_error,
    }


@celery_app.task(
    bind=True,
    name="hubra.core.tasks.backup_tasks.create_scheduled_backups",
)
def create_scheduled_backups_task(
    self, backup_type: str, triggered_by: str = "schedule"
) -> dict:
    """The scheduled run: one global backup plus one per active club."""
    from hubra.core.services.backup import BackupService

    records = BackupService.create_scheduled_backups(backup_type, triggered_by)
    failed = [r.tenant_slug or "global" for r in records if r.status != "completed"]
    if failed:
        logger.error("Scheduled %s backups failed for: %s", backup_type, failed)
    return {"count": len(records), "failed": failed}


@celery_app.task(
    bind=True,
    name="hubra.core.tasks.backup_tasks.restore_club_backup",
)
def restore_club_backup_task(
    self, record_id: int, sealed_key: str | None = None
) -> dict:
    """Restore one club from a club backup, keeping its current data aside."""
    from hubra.core.services.backup import BackupService, RestoreError

    try:
        record = BackupService.restore_club(record_id, _unseal(sealed_key))
    except RestoreError as exc:
        return {"id": record_id, "ok": False, "error": str(exc)}
    return {"id": record.id, "ok": True, "safety_schema": record.safety_schema}
