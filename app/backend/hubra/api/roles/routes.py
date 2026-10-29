"""Roles blueprint — CRUD and permission management for club roles."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from hubra.api.auth.helpers import get_current_member
from marshmallow import ValidationError
from hubra.api.permissions import (
    _current_member,
    filter_updatable_fields,
    member_is_admin,
    permission_required,
    can_update,
)
from hubra.api.utils import log_audit
from hubra.core.errors import api_error
from hubra.core.extensions import db
from hubra.core.schemas.role import RoleCreateSchema, RoleSchema
from hubra.api.roles.services import RoleService, RolesService

roles_bp = Blueprint("roles_bp", __name__)

_schema = RoleSchema()
_many_schema = RoleSchema(many=True)
_create_schema = RoleCreateSchema()


# ── GET /roles ────────────────────────────────────────────────────────────────


@roles_bp.get("/")
@jwt_required()
def list_roles():
    get_current_member()  # members of this club only
    return jsonify(_many_schema.dump(RolesService.list())), 200


# ── POST /roles ───────────────────────────────────────────────────────────────


@roles_bp.post("/")
@permission_required("roles", "create", "Create roles")
def create_role():
    body = request.get_json(silent=True) or {}
    try:
        data = _create_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    role = RolesService.create(data, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(_schema.dump(role)), 201


# ── PATCH /roles/<id> ─────────────────────────────────────────────────────────


@roles_bp.patch("/<int:role_id>")
@can_update("roles", "Update roles")
def update_role(role_id: int):
    role = RoleService.get(role_id)

    body = request.get_json(silent=True) or {}

    is_admin = member_is_admin(_current_member())

    if "is_admin" in body and not is_admin:
        return api_error("FORBIDDEN", "Only admins can change is_admin", 403)

    body = filter_updatable_fields(body)

    # Reject attempts to set is_system or is_owner via API
    if "is_system" in body or "is_owner" in body:
        return api_error("FORBIDDEN", "System role flags cannot be set via API", 403)

    name = body.get("name")
    if name is not None:
        if not isinstance(name, str) or not name.strip():
            return api_error("VALIDATION_ERROR", "name must be a non-empty string", 400)
        RoleService.update(role, name, get_current_member().id)

    if "description" in body:
        if body["description"] is not None and not isinstance(body["description"], str):
            return api_error("VALIDATION_ERROR", "description must be text", 400)
        role.description = body["description"]
    if "is_admin" in body and not isinstance(body["is_admin"], bool):
        # bool("no") is True: a string would have made the role an admin.
        return api_error("VALIDATION_ERROR", "is_admin must be true or false", 400)
    if "is_admin" in body and bool(body["is_admin"]) != role.is_admin:
        # An admin could otherwise take admin rights from the Owner role,
        # or make every member an admin through the Member role.
        if role.is_system or role.is_owner:
            return api_error(
                "ROLE_LOCKED", "A system role's admin rights cannot be changed", 409
            )
        role.is_admin = bool(body["is_admin"])
        log_audit(
            actor_id=get_current_member().id,
            action="update_role",
            target_type="Role",
            target_id=role.id,
            target_label=f"{role.name}: admin {'on' if role.is_admin else 'off'}",
        )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(_schema.dump(role)), 200


# ── DELETE /roles/<id> ────────────────────────────────────────────────────────


@roles_bp.delete("/<int:role_id>")
@permission_required("roles", "delete", "Delete roles")
def delete_role(role_id: int):
    RoleService.delete(role_id, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── GET /roles/<id>/permissions ───────────────────────────────────────────────


@roles_bp.get("/<int:role_id>/permissions")
@jwt_required()
def get_role_permissions(role_id: int):
    get_current_member()  # members of this club only
    perms = RoleService.get_permissions(role_id)
    return jsonify({"role_id": role_id, "permissions": perms}), 200


# ── PUT /roles/<id>/permissions ───────────────────────────────────────────────


@roles_bp.put("/<int:role_id>/permissions")
@permission_required("roles", "set_permissions", "Set role permissions")
def set_role_permissions(role_id: int):
    role = RoleService.get(role_id)

    body = request.get_json(silent=True) or {}
    perms = body.get("permissions")
    if not isinstance(perms, list):
        return api_error(
            "VALIDATION_ERROR", "'permissions' must be a list of strings", 400
        )

    sorted_perms = RoleService.set_permissions(role, perms, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify({"role_id": role_id, "permissions": sorted_perms}), 200
