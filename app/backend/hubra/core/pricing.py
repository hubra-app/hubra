"""Tier pricing calculation helpers.

Shared between the periodic invoice generation task and the bulk invoice endpoint.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP, ROUND_UP

logger = logging.getLogger(__name__)


def _get_yearly_expenses() -> Decimal:
    """Read the global Club.Finance.YearlyExpenses setting.

    Returns ``Decimal(0)`` on miss, empty, or error.
    """
    try:
        from sqlalchemy import select
        from hubra.core.extensions import db
        from hubra.core.models.setting import Setting

        s = db.session.scalar(
            select(Setting).where(Setting.key == "Club.Finance.YearlyExpenses")  # type: ignore[arg-type]
        )
        if s is not None and s.value:
            return Decimal(s.value)
    except Exception as exc:
        logger.warning("Could not load Club.Finance.YearlyExpenses: %s", exc)
    return Decimal(0)


_PERIODS = {"monthly": 12, "quarterly": 4, "half_yearly": 2, "yearly": 1}


def periods_per_year(billing_cycle: str | None) -> int:
    return _PERIODS.get(billing_cycle or "yearly", 1)


def period_window(today: date, billing_cycle: str | None):
    """First and last day of the billing period that contains ``today``."""
    months = 12 // periods_per_year(billing_cycle)
    first_month = (today.month - 1) // months * months + 1
    start = today.replace(month=first_month, day=1)
    last_month = first_month + months - 1
    end = (start.replace(month=last_month, day=28) + timedelta(days=4)).replace(
        day=1
    ) - timedelta(days=1)
    return start, end


def _plan_for(member, tier):
    """The member's payment plan, if it belongs to their current tier."""
    plan = getattr(member, "payment_plan", None)
    if plan is None or tier is None or plan.tier_id != tier.id:
        return None
    return plan


def billing_cycle_for(member, tier) -> str | None:
    """How often the member is billed: their plan's interval, else the tier's."""
    plan = _plan_for(member, tier)
    return plan.interval if plan else tier.billing_cycle


def annual_fee_for_member(member, tier) -> Decimal:
    """Calculate the annual fee for a member on a fixed or percentage tier."""
    if tier is None or not tier.billing_cycle:
        return Decimal(0)

    if tier.price_type == "fixed":
        if tier.price_chf is not None:
            return Decimal(str(tier.price_chf)) * periods_per_year(tier.billing_cycle)
        return Decimal(0)

    if tier.price_type == "percentage":
        if tier.percentage_value is not None:
            baseline = _get_yearly_expenses()
            return Decimal(str(tier.percentage_value)) / Decimal(100) * baseline
        return Decimal(0)

    return Decimal(0)


def calculate_invoice_amount(member, tier, deducted_annual_fees: Decimal) -> Decimal:
    """Return the invoice amount for one billing period for the given member.

    With a payment plan, the tier's yearly fee is split into the plan's
    periods, plus the plan's surcharge, rounded to 5 Rappen.
    """
    amount = tier_period_amount(member, tier, deducted_annual_fees)
    amount = apply_plan(amount, tier, _plan_for(member, tier))
    # An invoice is in whole Rappen: a percentage tier gives e.g. 27.7500 or
    # 8.3333..., which the QR bill refuses (it needs ###.##).
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def apply_plan(tier_amount: Decimal, tier, plan) -> Decimal:
    """Turn one tier-period amount into one plan-period amount."""
    if plan is None or tier_amount <= 0:
        return tier_amount
    annual = tier_amount * periods_per_year(tier.billing_cycle)
    surcharge = Decimal(1) + Decimal(str(plan.surcharge_pct or 0)) / Decimal(100)
    per_period = annual * surcharge / periods_per_year(plan.interval)
    return (per_period * 20).quantize(Decimal(1), rounding=ROUND_HALF_UP) / 20


def tier_period_amount(member, tier, deducted_annual_fees: Decimal) -> Decimal:
    """Invoice amount for one period of the tier's own billing cycle."""
    from sqlalchemy import select, func
    from hubra.core.extensions import db
    from hubra.core.models.member import Member

    periods = periods_per_year(tier.billing_cycle)

    if tier.price_type == "fixed":
        if tier.price_chf is None:
            return Decimal(0)
        return Decimal(str(tier.price_chf))

    if tier.price_type == "percentage":
        annual = annual_fee_for_member(member, tier)
        return annual / periods if periods else annual

    if tier.price_type == "formula":
        if tier.coefficient is None:
            return Decimal(0)
        baseline = _get_yearly_expenses()
        coefficient = Decimal(str(tier.coefficient))
        round_to_val = Decimal(str(tier.round_to)) if tier.round_to else Decimal(1)

        member_count = (
            db.session.scalar(
                select(func.count(Member.id))
                .where(Member.tier_id == tier.id)
                .where(Member.status == "active")
                .where(Member.archived_at.is_(None))
            )
            or 1
        )

        yearly_per_member = (baseline - coefficient * deducted_annual_fees) / Decimal(
            str(member_count)
        )
        amount = yearly_per_member / periods if periods else yearly_per_member

        if round_to_val > 0:
            factor = Decimal(1) / round_to_val
            amount = (amount * factor).to_integral_value(rounding=ROUND_UP) / factor

        return amount

    return Decimal(0)


def calculate_preview_cost(config: dict, db_session=None) -> dict:
    """Calculate per-member per-period cost from raw config values (no persisted tier).

    Returns: {amount, period, members, summary, amount_yearly}
    """
    from sqlalchemy import select, func
    from hubra.core.models.member import Member

    price_type = config.get("price_type", "fixed")
    billing_cycle = config.get("billing_cycle")
    periods = periods_per_year(billing_cycle)

    members = 0
    tier_id = config.get("tier_id")

    # A preview for a tier that doesn't exist yet has no tier_id.
    if db_session and isinstance(tier_id, int) and not isinstance(tier_id, bool):
        members = (
            db_session.scalar(
                select(func.count(Member.id))
                .where(Member.tier_id == tier_id)
                .where(Member.status == "active")
                .where(Member.archived_at.is_(None))
            )
            or 0
        )

    amount = Decimal(0)
    amount_yearly = Decimal(0)

    if price_type == "fixed":
        price = config.get("price_chf")
        if price is not None:
            amount = Decimal(str(price))
            amount_yearly = amount * periods

    elif price_type == "percentage":
        pct = config.get("percentage_value")
        baseline = _get_yearly_expenses()
        if pct is not None and baseline > 0:
            # Each member pays the full percentage, as the invoice job charges
            # (annual_fee_for_member); it is not split across the tier.
            amount_yearly = Decimal(str(pct)) / Decimal(100) * baseline
            amount = amount_yearly / periods if periods else amount_yearly

    elif price_type == "formula":
        coefficient = config.get("coefficient")
        round_to = config.get("round_to")
        deduct_ids = config.get("deduct_tier_ids", [])

        baseline = _get_yearly_expenses()
        if baseline > 0 and coefficient is not None:
            deducted = (
                total_deducted_annual_for_tiers(db_session, set(deduct_ids))
                if db_session and deduct_ids
                else Decimal(0)
            )
            mcount = max(members, 1)
            coefficient_d = Decimal(str(coefficient))
            baseline_d = baseline

            amount_yearly = (baseline_d - coefficient_d * deducted) / Decimal(
                str(mcount)
            )

            round_to_val = Decimal(str(round_to)) if round_to else Decimal(1)
            if round_to_val > 0:
                factor = Decimal(1) / round_to_val
                amount_yearly = (amount_yearly * factor).to_integral_value(
                    rounding=ROUND_UP
                ) / factor

            amount = amount_yearly / periods if periods else amount_yearly

    period_label = billing_cycle or "period"
    if amount > 0:
        summary = f"CHF {float(amount):.2f} / {period_label}"
    else:
        summary = "—"

    return {
        "amount": round(float(amount), 2),
        "amount_yearly": round(float(amount_yearly), 2),
        "period": billing_cycle,
        "members": members,
        "summary": summary,
    }


def deductions_by_tier(db_session):
    """A function giving, per formula tier, the yearly fees of the tiers it
    deducts: each tier its own ``deduct_tier_ids``, not all formula tiers'."""
    cache: dict[int, Decimal] = {}

    def for_tier(tier) -> Decimal:
        if tier is None or tier.price_type != "formula" or not tier.deduct_tier_ids:
            return Decimal(0)
        if tier.id not in cache:
            cache[tier.id] = total_deducted_annual_for_tiers(
                db_session, set(tier.deduct_tier_ids)
            )
        return cache[tier.id]

    return for_tier


def total_deducted_annual_for_tiers(session, tier_ids: set[int]) -> Decimal:
    """Calculate total annual fees from all active members in the given tier IDs.

    Used by formula-type tiers to determine how much other tiers contribute.
    """
    from sqlalchemy import select
    from hubra.core.models.member import Member

    if not tier_ids:
        return Decimal(0)

    # Deduct fixed-type tier fees only — percentage/formula tiers depend on
    # yearly expenses, so their "annual fee" is already derived from the same
    # global setting and would be circular to deduct.
    members = session.scalars(
        select(Member)
        .where(Member.tier_id.in_(tier_ids))
        .where(Member.status == "active")
        .where(Member.archived_at.is_(None))
    ).all()

    total = Decimal(0)
    for m in members:
        if m.tier is not None and m.tier.price_type == "fixed":
            total += annual_fee_for_member(m, m.tier)
    return total
