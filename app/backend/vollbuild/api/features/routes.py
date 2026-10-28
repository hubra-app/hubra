"""Features blueprint — read and toggle feature flags."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError

from vollbuild.api.features.services import FeatureFlagService
from vollbuild.api.permissions import permission_required, require_global_permission
from vollbuild.api.utils import log_audit
from vollbuild.errors import api_error
from vollbuild.extensions import db
from vollbuild.core.schemas.feature_flag import (
    FeatureFlagSchema,
    FeatureFlagWriteSchema,
    FeatureSchema,
    TenantFeatureSchema,
)

features_bp = Blueprint("features_bp", __name__)

_flag_schema = FeatureFlagSchema()
_flags_schema = FeatureFlagSchema(many=True)
_write_schema = FeatureFlagWriteSchema()
_feature_schema = FeatureSchema()
_feature_schema_list = FeatureSchema(many=True)
_tenant_feature_schema = TenantFeatureSchema()
_tenant_feature_schema_list = TenantFeatureSchema(many=True)


@features_bp.get("/")
@jwt_required()
def list_features():
    flags = FeatureFlagService.list()
    return jsonify(_flags_schema.dump(flags)), 200


@features_bp.put("/<string:key>")
@permission_required("features", "write", "Toggle feature flags")
def update_feature(key: str):
    body = request.get_json(silent=True) or {}
    try:
        data = _write_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    enabled = bool(data.get("enabled", False)) if isinstance(data, dict) else False

    flag = FeatureFlagService.set_enabled(key, enabled)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    log_audit(
        int(request.headers.get("X-User-Id", 0)),
        "toggle_feature",
        "feature_flag",
        None,
        key,
    )
    return jsonify(_flag_schema.dump(flag)), 200


# ── Manager: Feature catalog ─────────────────────────────────────────────────


@features_bp.get("/catalog")
@require_global_permission("features.read")
def list_feature_catalog():
    """List all features in the catalog."""
    features = FeatureFlagService.list_catalog()
    return jsonify(_feature_schema_list.dump(features)), 200


@features_bp.get("/tenants/<int:tenant_id>")
@require_global_permission("features.read")
def list_tenant_features(tenant_id: int):
    """List all feature grants for a tenant."""
    grants = FeatureFlagService.list_tenant_features(tenant_id)
    return jsonify(_tenant_feature_schema_list.dump(grants)), 200


@features_bp.put("/tenants/<int:tenant_id>/<string:feature_code>")
@require_global_permission("features.manage")
def set_tenant_feature_grant(tenant_id: int, feature_code: str):
    """Create or update a tenant feature grant."""
    body = request.get_json(silent=True) or {}
    enabled = bool(body.get("enabled", True))
    config = body.get("config")

    grant = FeatureFlagService.set_tenant_feature(
        tenant_id, feature_code, enabled, config
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    log_audit(
        int(getattr(g, "system_user", None) and g.system_user.id or 0),
        "set_tenant_feature",
        "tenant_feature",
        tenant_id,
        f"{tenant_id}:{feature_code}={enabled}",
    )
    return jsonify(_tenant_feature_schema.dump(grant)), 200
