"""Payment plans per membership tier."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from hubra.api.utils import log_audit
from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.member import Member, MembershipTier
from hubra.core.models.payment_plan import PLAN_INTERVALS, PaymentPlan
from hubra.core.pricing import (
    apply_plan,
    tier_period_amount,
    total_deducted_annual_for_tiers,
)


def plan_to_dict(plan: PaymentPlan) -> dict:
    return {
        "id": plan.id,
        "tier_id": plan.tier_id,
        "name": plan.name,
        "interval": plan.interval,
        "surcharge_pct": float(plan.surcharge_pct or 0),
        "visible": plan.visible,
    }


def _surcharge(value) -> Decimal:
    try:
        pct = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise_error(400, "VALIDATION_ERROR", "surcharge_pct must be a number")
    if not Decimal(0) <= pct <= Decimal(100):
        raise_error(400, "VALIDATION_ERROR", "surcharge_pct must be 0 to 100")
    return pct


def _apply(plan: PaymentPlan, data: dict, partial: bool) -> None:
    if "name" in data or not partial:
        name = (data.get("name") or "").strip()
        if not name:
            raise_error(400, "VALIDATION_ERROR", "name is required")
        plan.name = name
    if "interval" in data or not partial:
        if data.get("interval") not in PLAN_INTERVALS:
            raise_error(
                400, "VALIDATION_ERROR", f"interval must be one of {PLAN_INTERVALS}"
            )
        plan.interval = data["interval"]
    if "surcharge_pct" in data:
        plan.surcharge_pct = _surcharge(data["surcharge_pct"])
    if "visible" in data:
        plan.visible = bool(data["visible"])


class PaymentPlanService:
    @staticmethod
    def get(plan_id: int) -> PaymentPlan:
        plan = db.session.get(PaymentPlan, plan_id)
        if plan is None:
            raise_error(404, "NOT_FOUND", "Payment plan not found")
        return plan

    @staticmethod
    def create(tier: MembershipTier, data: dict, actor_id: int) -> PaymentPlan:
        plan = PaymentPlan(tier_id=tier.id, surcharge_pct=Decimal(0), visible=True)
        _apply(plan, data, partial=False)
        db.session.add(plan)
        db.session.flush()
        log_audit(actor_id, "create_payment_plan", "PaymentPlan", plan.id, plan.name)
        return plan

    @staticmethod
    def update(plan_id: int, data: dict, actor_id: int) -> PaymentPlan:
        plan = PaymentPlanService.get(plan_id)
        _apply(plan, data, partial=True)
        log_audit(actor_id, "update_payment_plan", "PaymentPlan", plan.id, plan.name)
        db.session.flush()
        return plan

    @staticmethod
    def delete(plan_id: int, actor_id: int) -> None:
        plan = PaymentPlanService.get(plan_id)
        log_audit(actor_id, "delete_payment_plan", "PaymentPlan", plan.id, plan.name)
        # Members on this plan fall back to the tier's billing cycle.
        db.session.query(Member).filter(Member.payment_plan_id == plan.id).update(
            {Member.payment_plan_id: None}
        )
        db.session.delete(plan)
        db.session.flush()

    @staticmethod
    def assign(member: Member, plan_id: int | None, actor_id: int, own: bool) -> None:
        """Put a member on a plan of their tier, or back on the tier's cycle."""
        if plan_id is not None:
            plan = PaymentPlanService.get(plan_id)
            if plan.tier_id != member.tier_id:
                raise_error(
                    400, "PLAN_NOT_FOR_TIER", "This plan belongs to another tier"
                )
            if own and not plan.visible:
                raise_error(403, "PLAN_NOT_AVAILABLE", "This plan is not available")
        member.payment_plan_id = plan_id
        log_audit(
            actor_id,
            "set_payment_plan",
            "Member",
            member.id,
            f"{member.name}: plan {plan_id or 'tier default'}",
        )
        db.session.flush()

    @staticmethod
    def options_for(member: Member) -> dict:
        """The member's tier, its visible plans with a price each, and the
        plan they are on."""
        tier = member.tier
        if tier is None:
            return {"tier": None, "current_plan_id": None, "plans": []}
        deducted = total_deducted_annual_for_tiers(
            db.session, set(tier.deduct_tier_ids or [])
        )
        base = tier_period_amount(member, tier, deducted)
        current = member.payment_plan_id
        plans = []
        for plan in tier.payment_plans:
            if not plan.visible and plan.id != current:
                continue
            data = plan_to_dict(plan)
            data["amount"] = float(apply_plan(base, tier, plan))
            plans.append(data)
        return {
            "tier": {
                "id": tier.id,
                "name": tier.name,
                "billing_cycle": tier.billing_cycle,
                "amount": float(base),
            },
            "current_plan_id": current,
            "plans": plans,
        }
