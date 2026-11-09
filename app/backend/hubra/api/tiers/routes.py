"""Tiers blueprint — membership tier CRUD."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from hubra.core.auth.helpers import get_current_member

from hubra.core.permissions import (
    permission_required,
    refuse_during_impersonation,
    require_member,
)
from hubra.core.utils import id_from_body, log_audit
from marshmallow import ValidationError
from hubra.core.errors import api_error, raise_error, validation_error
from hubra.core.extensions import db
from hubra.core.pricing import calculate_preview_cost
from hubra.core.schemas.member import (
    MemberSchema,
    MembershipTierCreateSchema,
    MembershipTierSchema,
)
from hubra.api.tiers.fee_adjustments import FeeAdjustmentService
from hubra.api.tiers.plans import PaymentPlanService, plan_to_dict
from hubra.api.tiers.services import TierService, TiersService
from hubra.core.models.member import Member

tiers_bp = Blueprint("tiers_bp", __name__)

_tier_schema = MembershipTierSchema()
_tiers_schema = MembershipTierSchema(many=True)
_create_schema = MembershipTierCreateSchema()
_members_schema = MemberSchema(many=True)


# ── POST /tiers/calculate-cost ────────────────────────────────────────────────


@tiers_bp.post("/calculate-cost")
@permission_required("tiers", "calculate_cost", "Calculate tier cost")
def tier_calculate_cost():
    body = dict(request.get_json(silent=True) or {})
    body["tier_id"] = id_from_body(body.get("tier_id"), "tier_id")
    try:
        result = calculate_preview_cost(body, db_session=db.session)
    except (ArithmeticError, TypeError, ValueError):
        return api_error("VALIDATION_ERROR", "Prices and factors must be numbers", 400)
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
        return validation_error(exc)

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
    db.session.commit()
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
    from hubra.api.members.routes import for_viewer

    return jsonify({"data": for_viewer(_members_schema.dump(members))}), 200


# ── Payment plans ─────────────────────────────────────────────────────────────


def _body() -> dict:
    return request.get_json(silent=True) or {}


@tiers_bp.get("/<int:tier_id>/plans")
@permission_required("tiers", "read", "View tiers")
def list_plans(tier_id: int):
    tier = TierService.get(tier_id)
    return jsonify([plan_to_dict(p) for p in tier.payment_plans]), 200


@tiers_bp.post("/<int:tier_id>/plans")
@permission_required("tiers", "update", "Update tiers")
def create_plan(tier_id: int):
    tier = TierService.get(tier_id)
    plan = PaymentPlanService.create(tier, _body(), get_current_member().id)
    db.session.commit()
    return jsonify(plan_to_dict(plan)), 201


@tiers_bp.patch("/plans/<int:plan_id>")
@permission_required("tiers", "update", "Update tiers")
def update_plan(plan_id: int):
    plan = PaymentPlanService.update(plan_id, _body(), get_current_member().id)
    db.session.commit()
    return jsonify(plan_to_dict(plan)), 200


@tiers_bp.delete("/plans/<int:plan_id>")
@permission_required("tiers", "update", "Update tiers")
def delete_plan(plan_id: int):
    PaymentPlanService.delete(plan_id, get_current_member().id)
    db.session.commit()
    return "", 204


@tiers_bp.put("/members/<int:member_id>/plan")
@permission_required("tiers", "update", "Update tiers")
def set_member_plan(member_id: int):
    member = db.session.get(Member, member_id)
    if member is None:
        return api_error("NOT_FOUND", "Member not found", 404)
    PaymentPlanService.assign(
        member, _body().get("plan_id"), get_current_member().id, own=False
    )
    db.session.commit()
    return jsonify(PaymentPlanService.options_for(member)), 200


@tiers_bp.get("/my-plan")
@require_member
def my_plan_options():
    return jsonify(PaymentPlanService.options_for(get_current_member())), 200


@tiers_bp.put("/my-plan")
@require_member
def choose_my_plan():
    member = get_current_member()
    PaymentPlanService.assign(member, _body().get("plan_id"), member.id, own=True)
    db.session.commit()
    return jsonify(PaymentPlanService.options_for(member)), 200


# ── A member's own fee (exempt, own amount, reduction) ───────────────────────


def _member_or_404(member_id: int) -> Member:
    member = db.session.get(Member, member_id)
    if member is None or member.archived_at is not None:
        raise_error(404, "NOT_FOUND", "Member not found")
    return member


@tiers_bp.get("/fee-adjustments")
@permission_required("fee_adjustments", "read", "View members' own fees")
def list_fee_adjustments():
    return jsonify(FeeAdjustmentService.list_all()), 200


@tiers_bp.get("/members/<int:member_id>/fee")
@permission_required("fee_adjustments", "read", "View members' own fees")
def get_member_fee(member_id: int):
    return jsonify(FeeAdjustmentService.get_for(_member_or_404(member_id))), 200


@tiers_bp.put("/members/<int:member_id>/fee")
@permission_required("fee_adjustments", "update", "Set members' own fees")
def set_member_fee(member_id: int):
    member = _member_or_404(member_id)
    FeeAdjustmentService.set(member, _body(), get_current_member().id)
    db.session.commit()
    return jsonify(FeeAdjustmentService.get_for(member)), 200


@tiers_bp.delete("/members/<int:member_id>/fee")
@permission_required("fee_adjustments", "update", "Set members' own fees")
def remove_member_fee(member_id: int):
    member = _member_or_404(member_id)
    FeeAdjustmentService.remove(member, get_current_member().id)
    db.session.commit()
    return jsonify(FeeAdjustmentService.get_for(member)), 200


@tiers_bp.get("/my-fee")
@require_member
def my_fee():
    return jsonify(FeeAdjustmentService.get_for(get_current_member())), 200


@tiers_bp.post("/my-fee/confirm")
@require_member
def confirm_my_fee():
    # Only the member can say that their reason still applies.
    refuse_during_impersonation()
    member = get_current_member()
    FeeAdjustmentService.confirm(member, _body())
    db.session.commit()
    return jsonify(FeeAdjustmentService.get_for(member)), 200
