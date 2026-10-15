"""Functions blueprint — CRUD and holder management for club functions/offices."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from vollbuild.api.auth.helpers import get_current_member

from vollbuild.api.functions.services import FunctionService
from vollbuild.api.permissions import permission_required
from vollbuild.api.utils import log_audit
from vollbuild.core.extensions import db

functions_bp = Blueprint("functions_bp", __name__)


@functions_bp.get("/")
@permission_required("functions", "read", "View functions")
def list_functions():
    fns = FunctionService.list_all()
    return jsonify([FunctionService.serialize(fn) for fn in fns]), 200


@functions_bp.get("/<int:function_id>")
@permission_required("functions", "read", "View functions")
def get_function(function_id: int):
    fn = FunctionService.get_by_id(function_id)
    return jsonify(FunctionService.serialize(fn)), 200


@functions_bp.post("/")
@permission_required("functions", "create", "Create functions")
def create_function():
    body = request.get_json(silent=True) or {}
    fn = FunctionService.create(
        name=body.get("name", ""),
        description=body.get("description"),
        max_holders=body.get("maxHolders", 1),
    )
    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="create_function",
        target_type="Function",
        target_id=fn.id,
        target_label=fn.name,
    )

    return jsonify(FunctionService.serialize(fn)), 201


@functions_bp.patch("/<int:function_id>")
@permission_required("functions", "update", "Update functions")
def update_function(function_id: int):
    body = request.get_json(silent=True) or {}
    field_map = {"maxHolders": "max_holders"}
    mapped = {field_map.get(k, k): v for k, v in body.items()}
    fn = FunctionService.update(function_id, **mapped)

    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="update_function",
        target_type="Function",
        target_id=fn.id,
        target_label=fn.name,
    )

    return jsonify(FunctionService.serialize(fn)), 200


@functions_bp.delete("/<int:function_id>")
@permission_required("functions", "delete", "Delete functions")
def delete_function(function_id: int):
    fn = FunctionService.get_by_id(function_id)
    name = fn.name

    FunctionService.delete(function_id)
    db.session.commit()

    log_audit(
        actor_id=get_current_member().id,
        action="delete_function",
        target_type="Function",
        target_id=function_id,
        target_label=name,
    )

    return jsonify({"ok": True}), 200


@functions_bp.post("/<int:function_id>/holders")
@permission_required("functions", "update", "Update functions")
def assign_holder(function_id: int):
    body = request.get_json(silent=True) or {}
    member_id = body.get("memberId")
    if not member_id:
        return jsonify({"error": "memberId is required"}), 400

    FunctionService.assign_holder(function_id, int(member_id))
    db.session.commit()

    fn = FunctionService.get_by_id(function_id)
    log_audit(
        actor_id=get_current_member().id,
        action="assign_function_holder",
        target_type="Function",
        target_id=function_id,
        target_label=fn.name,
    )

    return jsonify({"ok": True}), 201


@functions_bp.delete("/<int:function_id>/holders/<int:member_id>")
@permission_required("functions", "update", "Update functions")
def remove_holder(function_id: int, member_id: int):
    FunctionService.remove_holder(function_id, member_id)
    db.session.commit()

    fn = FunctionService.get_by_id(function_id)
    log_audit(
        actor_id=get_current_member().id,
        action="remove_function_holder",
        target_type="Function",
        target_id=function_id,
        target_label=fn.name,
    )

    return jsonify({"ok": True}), 200
