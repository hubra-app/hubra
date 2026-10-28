"""Audit blueprint — paginated read-only audit log."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from vollbuild.api.permissions import permission_required

from vollbuild.errors import api_error
from vollbuild.core.schemas.audit import AuditEntrySchema
from vollbuild.api.audit.services import AuditService, AuditsService

audit_bp = Blueprint("audit_bp", __name__)

_schema = AuditEntrySchema(many=True)
_one_schema = AuditEntrySchema()


# ── GET /audit ────────────────────────────────────────────────────────────────


@audit_bp.get("/")
@permission_required("audit", "read", "View audit log")
def list_audit():
    try:
        result = AuditsService.list(request.args, _schema)
    except ValueError as exc:
        return api_error("VALIDATION_ERROR", str(exc), 400)

    return jsonify(result), 200


# ── GET /audit/<id> ───────────────────────────────────────────────────────────


@audit_bp.get("/<int:entry_id>")
@permission_required("audit", "read", "View audit entries")
def get_audit_entry(entry_id: int):
    entry = AuditService.get(entry_id)
    return jsonify(_one_schema.dump(entry)), 200
