"""Tiers blueprint — membership tier CRUD."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from vollbuild.api.auth.helpers import get_current_member

from vollbuild.api.permissions import permission_required
from vollbuild.api.utils import log_audit
from marshmallow import ValidationError
from vollbuild.core.errors import api_error
from vollbuild.core.extensions import db
from vollbuild.core.pricing import calculate_preview_cost
from vollbuild.core.schemas.member import (
    MemberSchema,
    MembershipTierCreateSchema,
    MembershipTierSchema,
)
from vollbuild.api.tiers.services import TierService, TiersService

tiers_bp = Blueprint("tiers_bp", __name__)

_tier_schema = MembershipTierSchema()
_tiers_schema = MembershipTierSchema(many=True)
_create_schema = MembershipTierCreateSchema()
_members_schema = MemberSchema(many=True)


# ── POST /tiers/calculate-cost ────────────────────────────────────────────────


@tiers_bp.post("/calculate-cost")
@permission_required("tiers", "calculate_cost", "Calculate tier cost")
def tier_calculate_cost():
    body = request.get_json(silent=True) or {}
    result = calculate_preview_cost(body, db_session=db.session)
    return jsonify(result), 200


# ── GET /tiers ────────────────────────────────────────────────────────────────


@tiers_bp.get("/")
@permission_required("tiers", "read", "View tiers")
def list_tiers():
    return jsonify(_tiers_schema.dump(TiersService.list())), 200


# ── POST /tiers ───────────────────────────────────────────────────────────────


@tiers_bp.post("/")
@permission_required("tiers", "create", "Create tiers")
def create_tier():
    body = request.get_json(silent=True) or {}
    try:
        data = _create_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    tier = TiersService.create(data, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(_tier_schema.dump(tier)), 201


# ── PATCH /tiers/<id> ─────────────────────────────────────────────────────────


@tiers_bp.patch("/<int:tier_id>")
@permission_required("tiers", "update", "Update tiers")
def update_tier(tier_id: int):
    tier = TierService.get(tier_id)

    body = request.get_json(silent=True) or {}
    TierService.update(tier, body)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    log_audit(get_current_member().id, "update", "tier", tier.id, tier.name)
    return jsonify(_tier_schema.dump(tier)), 200


# ── DELETE /tiers/<id> ────────────────────────────────────────────────────────


@tiers_bp.delete("/<int:tier_id>")
@permission_required("tiers", "delete", "Delete tiers")
def delete_tier(tier_id: int):
    TierService.delete(tier_id, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── GET /tiers/<id>/members ───────────────────────────────────────────────────


@tiers_bp.get("/<int:tier_id>/members")
@permission_required("tiers", "read", "View tier members")
def list_tier_members(tier_id: int):
    TierService.get(tier_id)  # 404 if not found
    search = request.args.get("search", "").strip()
    members = TierService.list_members(tier_id, search)
    return jsonify({"data": _members_schema.dump(members)}), 200
