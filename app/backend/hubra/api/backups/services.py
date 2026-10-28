"""Backups API service layer."""

from __future__ import annotations

from hubra.core.services.backup import BackupService


class BackupsService:
    """Collection operations on backups — thin wrapper over BackupService."""

    @staticmethod
    def list(tenant_id: int | None = None) -> list:
        return BackupService.list_backups(tenant_id)

    @staticmethod
    def config_status() -> dict:
        return BackupService.get_config_status()


class BackupServiceAPI:
    """Single-backup operations — thin wrapper over BackupService."""

    @staticmethod
    def get(record_id: int):
        return BackupService.get_backup(record_id)

    @staticmethod
    def delete(record_id: int) -> None:
        BackupService.delete_backup(record_id)
