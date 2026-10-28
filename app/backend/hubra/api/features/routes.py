"""Module switches.

``modules_bp`` (club admins, ``/api/v1/modules``): list the modules with
their state, switch them on or off, and edit their settings.

``features_bp`` (platform managers, ``/api/v2/manager/features``): the
module catalog and per-club grants, including blocking a module for a club.
"""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request
from flask_jwt_extended import jwt_required

from hubra.api.auth.helpers import get_current_member
from hubra.api.permissions import permission_required, require_global_permission
from hubra.api.utils import log_audit
from hubra.core import modules
from hubra.core.errors import api_error
from hubra.core.extensions import db

modules_bp = Blueprint("modules_bp", __name__)
features_bp = Blueprint("features_bp", __name__)


def _commit():
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


# ── Club admins ──────────────────────────────────────────────────────────────


@modules_bp.get("/")
@jwt_required()
def list_modules():
    """All modules with their state for the current club.

    Every signed-in member needs this to build the navigation; settings
    values are only included for members who may change them.
    """
    from hubra.api.permissions import (
        _current_member,
        _derive_perm_key,
        _get_member_permission_keys,
        member_is_admin,
    )

    from hubra.api.auth.helpers import get_current_member

    member = get_current_member()  # members of this club only
    can_write = member is not None and (
        member_is_admin(member)
        or (
            hasattr(member, "roles")
            and _derive_perm_key("modules_bp", "modules", "write")
            in _get_member_permission_keys(member)
        )
    )
    data = []
    for state in modules.states().values():
        item = state.to_dict()
        if not can_write:
            item["config"] = {}
        data.append(item)
    return jsonify(data), 200


@modules_bp.put("/<string:code>")
@permission_required("modules", "write", "Switch modules on or off")
def switch_module(code: str):
    body = request.get_json(silent=True) or {}
    if not isinstance(body.get("enabled"), bool):
        return api_error("VALIDATION_ERROR", "enabled must be true or false", 400)
    state = modules.set_enabled(code, body["enabled"])
    log_audit(
        get_current_member().id,
        "enable_module" if body["enabled"] else "disable_module",
        "module",
        None,
        code,
    )
    _commit()
    return jsonify(state.to_dict()), 200


@modules_bp.put("/<string:code>/settings")
@permission_required("modules", "write", "Switch modules on or off")
def update_module_settings(code: str):
    body = request.get_json(silent=True) or {}
    config = body.get("config")
    if not isinstance(config, dict):
        return api_error("VALIDATION_ERROR", "config must be an object", 400)
    state = modules.set_config(code, config)
    log_audit(get_current_member().id, "update_module_settings", "module", None, code)
    _commit()
    return jsonify(state.to_dict()), 200


# ── Platform managers ────────────────────────────────────────────────────────


@features_bp.get("/catalog")
@require_global_permission("features.read")
def list_feature_catalog():
    """Every module the platform offers, with its default."""
    modules.registry.load()
    return jsonify([m.to_dict() for m in modules.registry.all()]), 200


@features_bp.get("/tenants/<int:tenant_id>")
@require_global_permission("features.read")
def list_tenant_features(tenant_id: int):
    """Module state for one club, as the club admin sees it plus ``allowed``."""
    return jsonify([s.to_dict() for s in modules.states(tenant_id).values()]), 200


@features_bp.put("/tenants/<int:tenant_id>/<string:feature_code>")
@require_global_permission("features.manage")
def set_tenant_feature_grant(tenant_id: int, feature_code: str):
    """Allow or block a module for a club, and optionally switch it.

    Body: ``{"allowed": bool?, "enabled": bool?, "config": {}?}``.
    """
    from hubra.core.models.tenant import Tenant

    if db.session.get(Tenant, tenant_id) is None:
        return api_error("NOT_FOUND", f"Tenant {tenant_id} not found", 404)
    modules.registry.load()
    if modules.registry.get(feature_code) is None:
        return api_error("NOT_FOUND", f"Module '{feature_code}' does not exist", 404)
    body = request.get_json(silent=True) or {}
    if "allowed" in body:
        modules.set_allowed(feature_code, bool(body["allowed"]), tenant_id)
    if "enabled" in body:
        modules.set_enabled(feature_code, bool(body["enabled"]), tenant_id)
    if isinstance(body.get("config"), dict):
        modules.set_config(feature_code, body["config"], tenant_id)
    state = modules.states(tenant_id)[feature_code]

    from hubra.core.models.tenant import GlobalAuditEntry

    db.session.add(
        GlobalAuditEntry(
            tenant_id=tenant_id,
            actor_id=getattr(getattr(g, "system_user", None), "id", None),
            action="set_tenant_module",
            target_type="module",
            target_id=feature_code,
            details={k: body[k] for k in ("allowed", "enabled") if k in body},
        )
    )
    _commit()
    return jsonify(state.to_dict()), 200
