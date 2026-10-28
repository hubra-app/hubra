"""Bindings blueprint — InternalKey + Binding CRUD, registry, validators."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from hubra.api.auth.helpers import get_current_member
from marshmallow import ValidationError
from sqlalchemy import select

from hubra.api.bindings.schemas import (
    BindingCreateSchema,
    BindingToggleSchema,
    BindingUpdateSchema,
    InternalKeyCreateSchema,
    InternalKeyUpdateSchema,
)
from hubra.api.bindings.services import (
    get_key,
    get_key_bindings_count,
    get_registry,
    get_validators,
    list_bindings,
    list_keys,
    list_sources,
    serialize_binding,
    serialize_key,
)
from hubra.api.permissions import permission_required
from hubra.api.utils import log_audit
from hubra.core.errors import api_error, raise_error
from hubra.core.extensions import db
from hubra.core.models.internal_key import InternalKey
from hubra.core.services.binding_engine import (
    create_binding,
    delete_binding,
    toggle_binding,
    update_binding,
)
from hubra.core.services.binding_registry import (
    build_attribute_registry,
    is_valid_attribute,
)
from hubra.core.validators import validate_value

logger = logging.getLogger(__name__)

bindings_bp = Blueprint("bindings_bp", __name__)

_key_create_schema = InternalKeyCreateSchema()
_key_update_schema = InternalKeyUpdateSchema()
_binding_create_schema = BindingCreateSchema()
_binding_update_schema = BindingUpdateSchema()
_binding_toggle_schema = BindingToggleSchema()


# ── GET /bindings/keys ────────────────────────────────────────────────────────


@bindings_bp.get("/keys")
@permission_required("keys", "read", "View internal keys")
def get_keys():
    return jsonify(list_keys()), 200


# ── POST /bindings/keys ───────────────────────────────────────────────────────


@bindings_bp.post("/keys")
@permission_required("keys", "write", "Create internal keys")
def create_key():
    body = request.get_json(silent=True) or {}
    try:
        data = _key_create_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    existing = db.session.scalar(
        select(InternalKey).where(InternalKey.key == data["key"])
    )
    if existing is not None:
        return api_error("CONFLICT", f"Key '{data['key']}' already exists", 409)

    ik = InternalKey(
        key=data["key"],
        allow_multiple=data.get("allow_multiple", False),
        is_protected=data.get("is_protected", False),
        label=data.get("label"),
    )
    db.session.add(ik)
    db.session.flush()

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    log_audit(get_current_member().id, "create", "internal_key", ik.id, ik.key)

    return jsonify(serialize_key(ik)), 201


# ── PUT /bindings/keys/<int:key_id> ──────────────────────────────────────────


@bindings_bp.put("/keys/<int:key_id>")
@permission_required("keys", "write", "Update internal keys")
def update_key(key_id: int):
    ik = get_key(key_id)
    if ik is None:
        raise_error(404, "NOT_FOUND", f"InternalKey {key_id} not found")

    body = request.get_json(silent=True) or {}
    try:
        data = _key_update_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    has_bindings = get_key_bindings_count(key_id) > 0

    if "allow_multiple" in data and data["allow_multiple"] != ik.allow_multiple:
        if ik.is_protected:
            return api_error(
                "PROTECTED",
                "Cannot change allow_multiple while key is protected. "
                "Unprotect the key first.",
                409,
            )
        if has_bindings:
            return api_error(
                "CONFLICT",
                "Cannot change allow_multiple while bindings exist",
                409,
            )
        ik.allow_multiple = data["allow_multiple"]

    if "label" in data:
        ik.label = data["label"]

    if "is_protected" in data and data["is_protected"] is not None:
        ik.is_protected = data["is_protected"]

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    log_audit(get_current_member().id, "update", "internal_key", key_id, ik.key)

    return jsonify(serialize_key(ik)), 200


# ── DELETE /bindings/keys/<int:key_id> ───────────────────────────────────────


@bindings_bp.delete("/keys/<int:key_id>")
@permission_required("keys", "delete", "Delete internal keys")
def delete_key(key_id: int):
    ik = get_key(key_id)
    if ik is None:
        raise_error(404, "NOT_FOUND", f"InternalKey {key_id} not found")

    if ik.is_protected:
        return api_error("PROTECTED", "Cannot delete a protected key", 409)

    if get_key_bindings_count(key_id) > 0:
        return api_error(
            "CONFLICT",
            "Cannot delete key with existing bindings. Remove bindings first.",
            409,
        )

    key_name = ik.key
    db.session.delete(ik)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    log_audit(get_current_member().id, "delete", "internal_key", key_id, key_name)

    return "", 204


# ── GET /bindings/ ───────────────────────────────────────────────────────────


@bindings_bp.get("/")
@permission_required("bindings", "read", "View bindings")
def get_bindings():
    key_id = request.args.get("key_id", type=int)
    binding_type = request.args.get("type")
    return jsonify(list_bindings(key_id=key_id, binding_type=binding_type)), 200


# ── POST /bindings/ ──────────────────────────────────────────────────────────


@bindings_bp.post("/")
@permission_required("bindings", "write", "Create bindings")
def create_binding_route():
    body = request.get_json(silent=True) or {}
    try:
        data = _binding_create_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    if not is_valid_attribute(data["type"], data["source_attribute"]):
        return api_error(
            "VALIDATION_ERROR",
            f"Attribute '{data['source_attribute']}' is not valid for type '{data['type']}'",
            400,
        )

    if data.get("validator", "none") != "none":
        from hubra.core.services.binding_registry import (
            WRITE_ONLY_ATTRIBUTES,
            resolve_source_value,
        )

        if data["source_attribute"] not in WRITE_ONLY_ATTRIBUTES:
            value = resolve_source_value(
                data["type"], data["source_id"], data["source_attribute"]
            )
            if value is not None:
                error = validate_value(data["validator"], value)
                if error:
                    return api_error(
                        "VALIDATION_ERROR",
                        f"Source value '{value}' failed validation: {error}",
                        400,
                    )

    binding = create_binding(
        type=data["type"],
        source_id=data["source_id"],
        source_attribute=data["source_attribute"],
        key_id=data["key_id"],
        validator=data.get("validator", "none"),
        enabled=data.get("enabled", True),
        is_protected=data.get("is_protected", False),
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    log_audit(
        get_current_member().id,
        "create",
        "binding",
        binding.id,
        f"{binding.type}:{binding.source_attribute}",
    )

    return jsonify(serialize_binding(binding)), 201


# ── PUT /bindings/<int:binding_id> ───────────────────────────────────────────


@bindings_bp.put("/<int:binding_id>")
@permission_required("bindings", "write", "Update bindings")
def update_binding_route(binding_id: int):
    body = request.get_json(silent=True) or {}
    try:
        data = _binding_update_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    fields = {k: v for k, v in data.items() if v is not None}

    if "type" in fields and "source_attribute" in fields:
        if not is_valid_attribute(fields["type"], fields["source_attribute"]):
            return api_error(
                "VALIDATION_ERROR",
                f"Attribute '{fields['source_attribute']}' is not valid for type '{fields['type']}'",
                400,
            )

    binding = update_binding(binding_id, **fields)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    log_audit(
        get_current_member().id,
        "update",
        "binding",
        binding.id,
        f"{binding.type}:{binding.source_attribute}",
    )

    return jsonify(serialize_binding(binding)), 200


# ── DELETE /bindings/<int:binding_id> ────────────────────────────────────────


@bindings_bp.delete("/<int:binding_id>")
@permission_required("bindings", "delete", "Delete bindings")
def delete_binding_route(binding_id: int):
    delete_binding(binding_id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    log_audit(
        get_current_member().id,
        "delete",
        "binding",
        binding_id,
        None,
    )

    return "", 204


# ── POST /bindings/<int:binding_id>/toggle ───────────────────────────────────


@bindings_bp.post("/<int:binding_id>/toggle")
@permission_required("bindings", "write", "Toggle bindings")
def toggle_binding_route(binding_id: int):
    body = request.get_json(silent=True) or {}
    try:
        data = _binding_toggle_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    binding = toggle_binding(binding_id, data["enabled"])

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    log_audit(
        get_current_member().id,
        "toggle",
        "binding",
        binding.id,
        f"enabled={data['enabled']}",
    )

    return jsonify(serialize_binding(binding)), 200


# ── GET /bindings/registry ───────────────────────────────────────────────────


@bindings_bp.get("/registry")
@permission_required("bindings", "read", "View binding registry")
def get_registry_route():
    return jsonify(get_registry()), 200


# ── GET /bindings/validators ─────────────────────────────────────────────────


@bindings_bp.get("/validators")
@permission_required("bindings", "read", "View validators")
def get_validators_route():
    return jsonify(get_validators()), 200


# ── GET /bindings/sources ────────────────────────────────────────────────────


@bindings_bp.get("/sources")
@permission_required("bindings", "read", "View binding sources")
def get_sources_route():
    binding_type = request.args.get("type")
    if not binding_type or binding_type not in build_attribute_registry():
        return api_error("VALIDATION_ERROR", f"Invalid type: {binding_type}", 400)
    return jsonify(list_sources(binding_type)), 200


# ── GET /bindings/preview ────────────────────────────────────────────────────


@bindings_bp.get("/preview")
@permission_required("bindings", "read", "Preview binding source values")
def preview_binding_value():
    from hubra.api.bindings.services import preview_source_value

    binding_type = request.args.get("type")
    source_id = request.args.get("source_id")
    source_attribute = request.args.get("source_attribute")
    if not binding_type or binding_type not in build_attribute_registry():
        return api_error("VALIDATION_ERROR", f"Invalid type: {binding_type}", 400)
    if not source_id:
        return api_error("VALIDATION_ERROR", "source_id is required", 400)
    if not source_attribute or not is_valid_attribute(binding_type, source_attribute):
        return api_error(
            "VALIDATION_ERROR", f"Invalid attribute: {source_attribute}", 400
        )
    return (
        jsonify(preview_source_value(binding_type, source_id, source_attribute)),
        200,
    )
