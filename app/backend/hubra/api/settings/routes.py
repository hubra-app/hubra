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


# ── GET /settings/club-profile ────────────────────────────────────────────────

# The parts of Settings > Verein every member may see (the rest, such as the
# membership rules, stays with GET /admin/club-settings).
_PUBLIC_CLUB_FIELDS = (
    "club_name",
    "club_description",
    "logo",
    "primary_color",
    "secondary_color",
    "accent_color",
    "timezone",
    "locale",
    "date_format",
)


@settings_bp.get("/club-profile")
@jwt_required()
def get_club_profile():
    """Name, look and announcement banner of the club, for every member."""
    from hubra.core.tenant.context import current_tenant

    get_current_member()  # members of this club only
    tenant = current_tenant()
    branding = dict((tenant.settings or {}).get("branding", {})) if tenant else {}
    profile = {k: branding.get(k) for k in _PUBLIC_CLUB_FIELDS}
    if not profile["club_name"] and tenant is not None:
        profile["club_name"] = tenant.name
    banner = (branding.get("announcement_banner_text") or "").strip()
    profile["banner"] = (
        banner if banner and branding.get("announcement_banner_active") else None
    )
    return jsonify(profile), 200


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

    if key == "mail.domain":
        err = _mail_domain_error(data.get("value"))
        if err:
            return api_error("DOMAIN_NOT_VERIFIED", err, 400)

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


def _mail_domain_error(value) -> str | None:
    """Why the club may not use *value* as its mail domain, if it may not.

    Mailboxes of every club live on one mail server, so a club's own mail
    domain has to be one it proved it owns (Settings › Domains). The
    platform's mail domain and its subdomains need no proof.
    """
    from flask import current_app
    from sqlalchemy import select

    from hubra.core.models.domain import Domain
    from hubra.core.tenant.context import current_tenant

    domain = str(value or "").strip().lower()
    current = str(SettingService.get("mail.domain") or "").strip().lower()
    platform = (current_app.config.get("MAIL_DOMAIN") or "hubra.club").lower()
    if not domain or domain == current:
        return None
    if domain == platform or domain.endswith(f".{platform}"):
        return None
    tenant = current_tenant()
    verified = tenant is not None and db.session.scalar(
        select(Domain.id).where(
            Domain.tenant_id == tenant.id,
            Domain.domain == domain,
            Domain.verified.is_(True),
        )
    )
    if verified:
        return None
    return (
        f"{domain} is not a verified domain of this club. Add and verify it "
        "under Settings › Domains first."
    )


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
