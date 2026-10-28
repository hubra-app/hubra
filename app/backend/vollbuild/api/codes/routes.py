"""Codes blueprint — CRUD for club-wide shared codes."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from vollbuild.api.auth.helpers import get_current_member

from marshmallow import ValidationError

from vollbuild.api.permissions import permission_required
from vollbuild.api.codes.services import CodeService, CodesService
from vollbuild.errors import api_error
from vollbuild.extensions import db
from vollbuild.core.schemas.code import (
    CodeCreateSchema,
    CodeSchema,
    CodeUpdateSchema,
)

codes_bp = Blueprint("codes_bp", __name__)

_code_schema = CodeSchema()
_codes_schema = CodeSchema(many=True)
_create_schema = CodeCreateSchema()
_update_schema = CodeUpdateSchema()


@codes_bp.get("/")
@permission_required("codes", "read", "View codes")
def list_codes():
    codes = CodesService.list()
    return jsonify(_codes_schema.dump(codes)), 200


@codes_bp.get("/<int:id>")
@permission_required("codes", "read", "View codes")
def get_code(id: int):
    code = CodeService.get_by_id(id)
    return jsonify(_code_schema.dump(code)), 200


@codes_bp.post("/")
@permission_required("codes", "create", "Create codes")
def create_code():
    body: dict = request.get_json(silent=True) or {}  # type: ignore[assignment]
    try:
        data = _create_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    code = CodesService.create(data, get_current_member().id)
    db.session.commit()
    return jsonify(_code_schema.dump(code)), 201


@codes_bp.patch("/<int:id>")
@permission_required("codes", "update", "Update codes")
def update_code(id: int):
    body: dict = request.get_json(silent=True) or {}  # type: ignore[assignment]
    try:
        data = _update_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    code = CodeService.get_by_id(id)
    CodeService.update(code, data, get_current_member().id)
    db.session.commit()
    return jsonify(_code_schema.dump(code)), 200


@codes_bp.delete("/<int:id>")
@permission_required("codes", "delete", "Delete codes")
def delete_code(id: int):
    code = CodeService.get_by_id(id)
    CodeService.delete(code)
    db.session.commit()
    return jsonify({"message": "Lock code deleted"}), 200
