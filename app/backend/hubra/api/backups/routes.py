"""Backups for the manager portal.

``platform_backups_bp`` (``/api/v1/manager/platform/backups``, also under
``/api/v2``): a backup dumps the whole database, every club included, so
only platform staff with the global permission ``backups.manage`` start,
verify or delete one.  Where they are stored is a platform setting
(``backup.s3.*``).
"""

from __future__ import annotations

import logging

from flask import Blueprint, current_app, g, jsonify, request

from hubra.api.backups.services import BackupsService, BackupServiceAPI
from hubra.api.permissions import require_global_permission
from hubra.core.errors import api_error
from hubra.core.extensions import db
from hubra.core.models.tenant import GlobalAuditEntry
from hubra.core.schemas.backup import BackupConfigSchema, BackupRecordSchema

logger = logging.getLogger(__name__)

platform_backups_bp = Blueprint("platform_backups_bp", __name__)

_PERM = "backups.manage"

_backup_schema = BackupRecordSchema()
_backups_schema = BackupRecordSchema(many=True)
_config_schema = BackupConfigSchema()


def _actor():
    return getattr(g, "system_user", None)


def _audit(action: str, record_id: int | None, details: dict | None = None) -> None:
    db.session.add(
        GlobalAuditEntry(
            tenant_id=None,
            actor_id=getattr(_actor(), "id", None),
            action=f"backup.{action}",
            target_type="backup",
            target_id=str(record_id) if record_id is not None else None,
            details=details or {},
            ip_address=request.remote_addr,
        )
    )
    db.session.commit()


@platform_backups_bp.get("/")
@require_global_permission(_PERM)
def list_backups():
    """All backup records, newest first."""
    records = BackupsService.list()
    return jsonify(_backups_schema.dump(records)), 200


@platform_backups_bp.post("/")
@require_global_permission(_PERM)
def create_backup():
    """Start a manual backup via Celery. Returns 202 with the task ID."""
    from hubra.core.tasks.backup_tasks import create_backup_task

    actor = _actor()
    triggered_by = (getattr(actor, "email", None) or "platform") if actor else "platform"

    if current_app.config.get("TESTING"):
        from hubra.core.services.backup import BackupService

        record = BackupService.create_backup(
            backup_type="manual", triggered_by=triggered_by
        )
        _audit("create", record.id)
        return jsonify(_backup_schema.dump(record)), 201

    task = create_backup_task.delay(backup_type="manual", triggered_by=triggered_by)
    _audit("create", None, {"task_id": task.id})
    return jsonify({"task_id": task.id, "status": "pending"}), 202


@platform_backups_bp.get("/config")
@require_global_permission(_PERM)
def get_config():
    """S3 connection and encryption status."""
    status = BackupsService.config_status()
    return jsonify(_config_schema.dump(status)), 200


@platform_backups_bp.get("/<int:record_id>")
@require_global_permission(_PERM)
def get_backup(record_id: int):
    record = BackupServiceAPI.get(record_id)
    if record is None:
        return api_error("NOT_FOUND", "Backup record not found", 404)
    return jsonify(_backup_schema.dump(record)), 200


@platform_backups_bp.post("/<int:record_id>/verify")
@require_global_permission(_PERM)
def verify_backup(record_id: int):
    """Start a verification via Celery. Returns 202."""
    record = BackupServiceAPI.get(record_id)
    if record is None:
        return api_error("NOT_FOUND", "Backup record not found", 404)
    if record.status != "completed":
        return api_error("CONFLICT", "Only completed backups can be verified", 409)

    if current_app.config.get("TESTING"):
        from hubra.core.services.backup import BackupService

        updated = BackupService.verify_backup(record_id)
        _audit("verify", record_id)
        return jsonify(_backup_schema.dump(updated)), 200

    from hubra.core.tasks.backup_tasks import verify_backup_task

    task = verify_backup_task.delay(record_id)
    _audit("verify", record_id)
    return jsonify(
        {"task_id": task.id, "record_id": record_id, "status": "verifying"}
    ), 202


@platform_backups_bp.delete("/<int:record_id>")
@require_global_permission(_PERM)
def delete_backup(record_id: int):
    """Delete a backup (S3 object and record)."""
    record = BackupServiceAPI.get(record_id)
    if record is None:
        return api_error("NOT_FOUND", "Backup record not found", 404)

    try:
        BackupServiceAPI.delete(record_id)
    except ValueError as exc:
        return api_error("NOT_FOUND", str(exc), 404)

    _audit("delete", record_id)
    return "", 204
