"""Backups for the manager portal.

``platform_backups_bp`` (``/api/v1/manager/platform/backups``): platform staff with the global permission ``backups.manage``
start, verify, restore and delete backups.  A backup is either global (the
public schema) or one club's schema; a club backup can be restored on its
own, after typing the club's address to confirm.  Where backups are stored
is a platform setting (``backup.s3.*``).
"""

from __future__ import annotations

import logging

from flask import Blueprint, current_app, g, jsonify, request

from hubra.api.backups.services import BackupsService, BackupServiceAPI
from hubra.api.permissions import require_global_permission
from hubra.core.errors import api_error
from hubra.core.extensions import db
from hubra.core.models.tenant import GlobalAuditEntry, Tenant
from hubra.core.schemas.backup import BackupConfigSchema, BackupRecordSchema

logger = logging.getLogger(__name__)

platform_backups_bp = Blueprint("platform_backups_bp", __name__)

_PERM = "backups.manage"

_backup_schema = BackupRecordSchema()
_backups_schema = BackupRecordSchema(many=True)
_config_schema = BackupConfigSchema()


def _private_key(data: dict) -> tuple[str | None, object | None]:
    """The age private key the operator pasted, or an error response."""
    from hubra.core.services.backup_crypto import private_keys_in, valid_private_key

    raw = data.get("private_key")
    if raw in (None, ""):
        return None, None
    keys = private_keys_in(raw) if isinstance(raw, str) else []
    if not keys or not all(valid_private_key(k) for k in keys):
        return None, api_error(
            "VALIDATION_ERROR",
            "That is not an age private key (AGE-SECRET-KEY-1...)",
            400,
        )
    return raw, None


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
    """Backup records, newest first (``?tenant_id=`` for one club's)."""
    tenant_id = request.args.get("tenant_id", type=int)
    records = BackupsService.list(tenant_id)
    return jsonify(_backups_schema.dump(records)), 200


@platform_backups_bp.post("/")
@require_global_permission(_PERM)
def create_backup():
    """Start a manual backup via Celery. Returns 202 with the task ID.

    Body ``{"tenant_id": N}`` backs up that club; without it the global
    (public schema) backup is made.
    """
    from hubra.core.tasks.backup_tasks import create_backup_task

    data = request.get_json(silent=True) or {}
    tenant_id = data.get("tenant_id")
    if tenant_id is not None:
        if not isinstance(tenant_id, int) or isinstance(tenant_id, bool):
            return api_error("VALIDATION_ERROR", "tenant_id must be a number", 400)
        if db.session.get(Tenant, tenant_id) is None:
            return api_error("NOT_FOUND", "Club not found", 404)
    details = {"tenant_id": tenant_id} if tenant_id is not None else {}

    actor = _actor()
    triggered_by = (
        (getattr(actor, "email", None) or "platform") if actor else "platform"
    )

    if current_app.config.get("TESTING"):
        from hubra.core.services.backup import BackupService

        record = BackupService.create_backup(
            backup_type="manual", triggered_by=triggered_by, tenant_id=tenant_id
        )
        _audit("create", record.id, details)
        return jsonify(_backup_schema.dump(record)), 201

    task = create_backup_task.delay(
        backup_type="manual", triggered_by=triggered_by, tenant_id=tenant_id
    )
    _audit("create", None, {"task_id": task.id, **details})
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
    private_key, error = _private_key(request.get_json(silent=True) or {})
    if error:
        return error

    if current_app.config.get("TESTING"):
        from hubra.core.services.backup import BackupService

        updated = BackupService.verify_backup(record_id, private_key)
        _audit("verify", record_id)
        return jsonify(_backup_schema.dump(updated)), 200

    from hubra.core.crypto import seal
    from hubra.core.tasks.backup_tasks import verify_backup_task

    task = verify_backup_task.delay(
        record_id, seal(private_key) if private_key else None
    )
    _audit("verify", record_id)
    return jsonify(
        {"task_id": task.id, "record_id": record_id, "status": "verifying"}
    ), 202


@platform_backups_bp.post("/<int:record_id>/restore")
@require_global_permission(_PERM)
def restore_backup(record_id: int):
    """Restore one club from a club backup.  Returns 202 (200 when TESTING).

    Body ``{"confirm": "<club address>", "private_key": "AGE-SECRET-KEY-1..."}``:
    the club's current slug, typed by hand, and for an age backup the backup
    private key (unless it is on the server).  The key is used for this
    restore only and never stored; on its way to the worker it is sealed
    with the server key and expires after an hour.  The club's current data
    is kept as a safety copy schema.
    """
    record = BackupServiceAPI.get(record_id)
    if record is None:
        return api_error("NOT_FOUND", "Backup record not found", 404)
    if record.scope != "club" or record.tenant_id is None:
        return api_error(
            "CONFLICT", "Only a backup of an existing club can be restored", 409
        )
    if record.status != "completed":
        return api_error("CONFLICT", "Only completed backups can be restored", 409)
    tenant = db.session.get(Tenant, record.tenant_id)
    data = request.get_json(silent=True) or {}
    if tenant is None or data.get("confirm") != tenant.slug:
        return api_error(
            "VALIDATION_ERROR", "Type the club's address to confirm the restore", 400
        )
    private_key, error = _private_key(data)
    if error:
        return error
    from hubra.core.services.backup_crypto import needs_private_key

    if needs_private_key(record.s3_key) and not private_key:
        return api_error(
            "PRIVATE_KEY_REQUIRED",
            "This backup can only be opened with the backup private key",
            400,
        )
    details = {"tenant_id": tenant.id, "slug": tenant.slug}

    if current_app.config.get("TESTING"):
        from hubra.core.services.backup import BackupService, RestoreError

        try:
            updated = BackupService.restore_club(record_id, private_key)
        except RestoreError as exc:
            _audit("restore_failed", record_id, {**details, "error": str(exc)})
            return api_error("RESTORE_FAILED", str(exc), 500)
        _audit("restore", record_id, details)
        return jsonify(_backup_schema.dump(updated)), 200

    from hubra.core.crypto import seal
    from hubra.core.tasks.backup_tasks import restore_club_backup_task

    task = restore_club_backup_task.delay(
        record_id, seal(private_key) if private_key else None
    )
    _audit("restore", record_id, {**details, "task_id": task.id})
    return jsonify(
        {"task_id": task.id, "record_id": record_id, "status": "restoring"}
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
