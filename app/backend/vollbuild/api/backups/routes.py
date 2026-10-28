"""Backups blueprint — admin-only endpoints for database backup management."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify
from flask_jwt_extended import current_user
from vollbuild.api.auth.helpers import get_current_member

from vollbuild.api.permissions import require_admin
from vollbuild.api.utils import log_audit
from vollbuild.errors import api_error
from vollbuild.core.schemas.backup import BackupRecordSchema, BackupConfigSchema
from vollbuild.api.backups.services import BackupsService, BackupServiceAPI

logger = logging.getLogger(__name__)

backups_bp = Blueprint("backups_bp", __name__)

_backup_schema = BackupRecordSchema()
_backups_schema = BackupRecordSchema(many=True)
_config_schema = BackupConfigSchema()


@backups_bp.get("/")
@require_admin
def list_backups():
    """List all backup records, newest first."""
    records = BackupsService.list()
    return jsonify(_backups_schema.dump(records)), 200


@backups_bp.post("/")
@require_admin
def create_backup():
    """Trigger a manual backup via Celery. Returns 202 with the new record ID."""
    from vollbuild.core.tasks.backup_tasks import create_backup_task

    member = current_user
    triggered_by = f"{member.first_name} {member.last_name}" if member else "admin"

    from flask import current_app

    if current_app.config.get("TESTING"):
        from vollbuild.core.services.backup import BackupService

        record = BackupService.create_backup(
            backup_type="manual", triggered_by=triggered_by
        )
        log_audit(
            get_current_member().id, "create", "backup", record.id, str(record.id)
        )
        return jsonify(_backup_schema.dump(record)), 201

    task = create_backup_task.delay(backup_type="manual", triggered_by=triggered_by)
    log_audit(get_current_member().id, "create", "backup", None, task.id)
    return jsonify({"task_id": task.id, "status": "pending"}), 202


@backups_bp.get("/config")
@require_admin
def get_config():
    """Return S3 connection + encryption configuration status."""
    status = BackupsService.config_status()
    return jsonify(_config_schema.dump(status)), 200


@backups_bp.get("/<int:record_id>")
@require_admin
def get_backup(record_id: int):
    """Get a single backup record."""
    record = BackupServiceAPI.get(record_id)
    if record is None:
        return api_error("NOT_FOUND", "Backup record not found", 404)
    return jsonify(_backup_schema.dump(record)), 200


@backups_bp.post("/<int:record_id>/verify")
@require_admin
def verify_backup(record_id: int):
    """Trigger backup verification via Celery. Returns 202."""
    record = BackupServiceAPI.get(record_id)
    if record is None:
        return api_error("NOT_FOUND", "Backup record not found", 404)
    if record.status != "completed":
        return api_error(
            "CONFLICT",
            "Only completed backups can be verified",
            409,
        )

    from flask import current_app

    if current_app.config.get("TESTING"):
        from vollbuild.core.services.backup import BackupService

        updated = BackupService.verify_backup(record_id)
        log_audit(
            get_current_member().id, "verify", "backup", record_id, str(record_id)
        )
        return jsonify(_backup_schema.dump(updated)), 200

    from vollbuild.core.tasks.backup_tasks import verify_backup_task

    task = verify_backup_task.delay(record_id)
    log_audit(get_current_member().id, "verify", "backup", record_id, str(record_id))
    return jsonify(
        {"task_id": task.id, "record_id": record_id, "status": "verifying"}
    ), 202


@backups_bp.delete("/<int:record_id>")
@require_admin
def delete_backup(record_id: int):
    """Delete a backup (S3 object + DB record)."""
    record = BackupServiceAPI.get(record_id)
    if record is None:
        return api_error("NOT_FOUND", "Backup record not found", 404)

    try:
        BackupServiceAPI.delete(record_id)
    except ValueError as exc:
        return api_error("NOT_FOUND", str(exc), 404)

    log_audit(get_current_member().id, "delete", "backup", record_id, str(record_id))
    return "", 204
