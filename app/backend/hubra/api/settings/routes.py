"""Settings blueprint — KV store CRUD."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from hubra.api.auth.helpers import get_current_member
from marshmallow import ValidationError

from hubra.api.permissions import (
    _current_member,
    _get_member_permission_keys,
    member_is_admin,
)
from hubra.api.utils import log_audit
from hubra.core.errors import api_error
from hubra.core.extensions import db
from hubra.core.schemas.settings import SettingSchema, SettingWriteSchema
from hubra.api.settings.services import SettingService, SettingsService

logger = logging.getLogger(__name__)

settings_bp = Blueprint("settings_bp", __name__)

_setting_schema = SettingSchema()
_settings_schema = SettingSchema(many=True)
_write_schema = SettingWriteSchema()

# New keys with these prefixes always land in this namespace, so writing
# "general" settings can't create, say, the IBAN printed on QR bills.
_RESERVED_NAMESPACES = {
    "Club.Banking.": "finance",
    "mail.": "mail",
    "I18n.": "I18n",
}


# ── GET /settings ─────────────────────────────────────────────────────────────


@settings_bp.get("/")
@jwt_required()
def get_settings():
    get_current_member()  # members of this club only
    all_settings = SettingsService.list()

    member = _current_member()
    if member_is_admin(member):
        return jsonify(_settings_schema.dump(all_settings)), 200

    roles = getattr(member, "roles", None)
    if roles:
        perms = _get_member_permission_keys(member)
        namespaces, key_map = SettingService.get_readable_namespaces_and_keys(perms)
        if namespaces is None:
            return jsonify(_settings_schema.dump(all_settings)), 200

        filtered: list = []
        for s in all_settings:
            ns = s.namespace
            if ns in namespaces:
                filtered.append(s)
            elif ns in key_map and s.key in key_map[ns]:
                filtered.append(s)
        return jsonify(_settings_schema.dump(filtered)), 200

    return jsonify([]), 200


# ── PUT /settings/<key> ───────────────────────────────────────────────────────


@settings_bp.put("/<string:key>")
@jwt_required()
def upsert_setting(key: str):
    get_current_member()  # members of this club only
    body = request.get_json(silent=True) or {}
    try:
        data = _write_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    if not member_is_admin(_current_member()):
        perms = _get_member_permission_keys(_current_member())
        # An existing setting is checked in the namespace it lives in, never
        # one the request names; how a setting is kept (namespace, secret,
        # locked, required, its type) is for admins to change.
        existing = SettingService.get_setting(key)
        if existing is not None:
            ns = existing.namespace or "general"
            for field in (
                "namespace",
                "sensitive",
                "required",
                "restricted",
                "validation_type",
            ):
                data.pop(field, None)
        else:
            ns = _RESERVED_NAMESPACES.get(
                next((p for p in _RESERVED_NAMESPACES if key.startswith(p)), ""),
                data.get("namespace") or "general",
            )
            data["namespace"] = ns
            data.pop("restricted", None)
            data.pop("required", None)
        if not SettingService.can_write(ns, key, perms):
            return api_error(
                "FORBIDDEN",
                "Insufficient permissions to write this setting",
                403,
            )

    setting = SettingService.upsert(key, data)

    err = SettingService.validate_value(setting.validation_type, data.get("value", ""))
    if err:
        db.session.rollback()
        return api_error("VALIDATION_ERROR", err, 400)

    log_audit(get_current_member().id, "upsert", "setting", None, key)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(_setting_schema.dump(setting)), 200


# ── DELETE /settings/<key> ────────────────────────────────────────────────────


@settings_bp.delete("/<string:key>")
@jwt_required()
def delete_setting(key: str):
    get_current_member()  # members of this club only
    if not member_is_admin(_current_member()):
        perms = _get_member_permission_keys(_current_member())
        setting = SettingService.get_setting(key)
        if setting and not SettingService.can_delete(setting.namespace, key, perms):
            return api_error(
                "FORBIDDEN",
                "Insufficient permissions to delete this setting",
                403,
            )

    SettingService.delete(key)
    log_audit(get_current_member().id, "delete", "setting", None, key)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── POST /settings/<key>/revert ──────────────────────────────────────────────


@settings_bp.post("/<string:key>/revert")
@jwt_required()
def revert_setting(key: str):
    get_current_member()  # members of this club only
    if not member_is_admin(_current_member()):
        perms = _get_member_permission_keys(_current_member())
        setting = SettingService.get_setting(key)
        if setting and not SettingService.can_write(setting.namespace, key, perms):
            return api_error(
                "FORBIDDEN",
                "Insufficient permissions to revert this setting",
                403,
            )

    setting = SettingService.revert_to_default(key)  # 404 / 409 as ApiError
    log_audit(get_current_member().id, "revert", "setting", None, key)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return jsonify(_setting_schema.dump(setting)), 200
