"""Settings blueprint — KV store CRUD."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from vollbuild.api.auth.helpers import get_current_member
from marshmallow import ValidationError

from vollbuild.api.permissions import (
    _current_member,
    _get_member_permission_keys,
    member_is_admin,
)
from vollbuild.api.utils import log_audit
from vollbuild.core.errors import api_error
from vollbuild.core.extensions import db
from vollbuild.core.schemas.settings import SettingSchema, SettingWriteSchema
from vollbuild.api.settings.services import SettingService, SettingsService

logger = logging.getLogger(__name__)

settings_bp = Blueprint("settings_bp", __name__)

_setting_schema = SettingSchema()
_settings_schema = SettingSchema(many=True)
_write_schema = SettingWriteSchema()


# ── GET /settings ─────────────────────────────────────────────────────────────


@settings_bp.get("/")
@jwt_required()
def get_settings():
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
    body = request.get_json(silent=True) or {}
    try:
        data = _write_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    if not member_is_admin(_current_member()):
        perms = _get_member_permission_keys(_current_member())
        ns = data.get("namespace") or "general"
        if not SettingService.can_write(ns, key, perms):
            return api_error(
                "FORBIDDEN",
                "Insufficient permissions to write this setting",
                403,
            )

    setting = SettingService.upsert(key, data)

    err = SettingService.validate_value(setting.validation_type, data.get("value", ""))
    if err:
        return api_error("VALIDATION_ERROR", err, 400)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    log_audit(get_current_member().id, "upsert", "setting", None, key)

    return jsonify(_setting_schema.dump(setting)), 200


# ── DELETE /settings/<key> ────────────────────────────────────────────────────


@settings_bp.delete("/<string:key>")
@jwt_required()
def delete_setting(key: str):
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

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    log_audit(get_current_member().id, "delete", "setting", None, key)
    return "", 204


# ── POST /settings/<key>/revert ──────────────────────────────────────────────


@settings_bp.post("/<string:key>/revert")
@jwt_required()
def revert_setting(key: str):
    if not member_is_admin(_current_member()):
        perms = _get_member_permission_keys(_current_member())
        setting = SettingService.get_setting(key)
        if setting and not SettingService.can_write(setting.namespace, key, perms):
            return api_error(
                "FORBIDDEN",
                "Insufficient permissions to revert this setting",
                403,
            )

    try:
        setting = SettingService.revert_to_default(key)
    except Exception as exc:
        status = getattr(exc, "code", 500)
        return api_error(
            "REVERT_FAILED", str(exc), status if isinstance(status, int) else 500
        )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    log_audit(get_current_member().id, "revert", "setting", None, key)
    return jsonify(_setting_schema.dump(setting)), 200
