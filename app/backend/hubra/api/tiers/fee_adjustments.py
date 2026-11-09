"""A member's own membership fee: exempt, a yearly amount, or a reduction.

The board sets it on the member's page with a reason and an optional end
date. Before the end date (``remind_days``, 30 by default) the member is
asked to confirm that the reason still applies; the board sees the answer
and can extend the date. From the first billing period that starts after
the end date the member pays the tier's fee again.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import NoReturn

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.fee_adjustment import (
    DEFAULT_REMIND_DAYS,
    FEE_ADJUSTMENT_KINDS,
    MemberFeeAdjustment,
    member_link,
)
from hubra.core.models.member import Member
from hubra.core.pricing import (
    apply_fee_adjustment,
    apply_plan,
    billing_cycle_for,
    tier_period_amount,
    total_deducted_annual_for_tiers,
)
from hubra.core.utils import log_audit

MAX_REASON = 2000
MAX_NOTE = 2000


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def fee_amounts(member: Member, on: date | None = None) -> dict:
    """The member's fee for one of their billing periods: the standard one
    (tier and payment plan) and what they pay with their own arrangement."""
    tier = member.tier
    if tier is None or not tier.billing_cycle:
        return {"billing_cycle": None, "standard_amount": None, "amount": None}
    deducted = total_deducted_annual_for_tiers(
        db.session, set(tier.deduct_tier_ids or [])
    )
    plan = member.payment_plan
    if plan is not None and plan.tier_id != tier.id:
        plan = None
    standard = apply_plan(tier_period_amount(member, tier, deducted), tier, plan)
    amount = apply_fee_adjustment(member, tier, standard, on or date.today())
    return {
        "billing_cycle": billing_cycle_for(member, tier),
        "standard_amount": float(round(standard, 2)),
        "amount": float(round(amount, 2)),
    }


def adjustment_to_dict(adj: MemberFeeAdjustment, today: date | None = None) -> dict:
    today = today or date.today()
    ended = adj.valid_until is not None and adj.valid_until < today
    return {
        "id": adj.id,
        "member_id": adj.member_id,
        "kind": adj.kind,
        "amount_chf": float(adj.amount_chf) if adj.amount_chf is not None else None,
        "percent": float(adj.percent) if adj.percent is not None else None,
        "reason": adj.reason,
        "valid_until": _iso(adj.valid_until),
        "remind_days": adj.remind_days,
        "reminder_sent_at": _iso(adj.reminder_sent_at),
        "confirmed_at": _iso(adj.confirmed_at),
        "confirmation_note": adj.confirmation_note,
        "active": not ended,
        "ended": ended,
        # Asked to confirm, not answered yet, and still running.
        "awaiting_confirmation": bool(
            adj.reminder_sent_at and not adj.confirmed_at and not ended
        ),
        "created_at": _iso(adj.created_at),
        "updated_at": _iso(adj.updated_at),
    }


def _get(member: Member) -> MemberFeeAdjustment | None:
    return db.session.scalar(
        select(MemberFeeAdjustment).where(MemberFeeAdjustment.member_id == member.id)
    )


def _bad(field: str, message: str) -> NoReturn:
    raise_error(400, "VALIDATION_ERROR", message, {field: [message]})


def _decimal(value, field: str, low: Decimal, high: Decimal | None) -> Decimal:
    if isinstance(value, bool):
        _bad(field, f"{field} must be a number")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        _bad(field, f"{field} must be a number")
    if not number.is_finite() or number < low or (high is not None and number > high):
        bound = f"{low} to {high}" if high is not None else f"at least {low}"
        _bad(field, f"{field} must be {bound}")
    return number


def _text(value, field: str, limit: int, required: bool) -> str | None:
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = value.strip()
    else:
        _bad(field, f"{field} must be text")
    if required and not text:
        _bad(field, f"{field} is required")
    if len(text) > limit:
        _bad(field, f"{field} is longer than {limit}")
    return text or None


def _date(value, field: str) -> date | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        _bad(field, f"{field} must be a date")
    try:
        return date.fromisoformat(value)
    except ValueError:
        _bad(field, f"{field} must be a date")


class FeeAdjustmentService:
    @staticmethod
    def get_for(member: Member) -> dict:
        """The member's arrangement (or None) and their fee with and without it."""
        adj = _get(member)
        return {
            "adjustment": adjustment_to_dict(adj) if adj else None,
            **fee_amounts(member),
        }

    @staticmethod
    def set(member: Member, data: dict, actor_id: int) -> MemberFeeAdjustment:
        """Create or replace the member's arrangement."""
        kind = data.get("kind")
        if kind not in FEE_ADJUSTMENT_KINDS:
            _bad("kind", f"kind must be one of {FEE_ADJUSTMENT_KINDS}")
        amount = percent = None
        if kind == "amount":
            amount = _decimal(data.get("amount_chf"), "amount_chf", Decimal(0), None)
        elif kind == "percent":
            percent = _decimal(data.get("percent"), "percent", Decimal(0), Decimal(100))
        reason = _text(data.get("reason"), "reason", MAX_REASON, required=True)
        valid_until = _date(data.get("valid_until"), "valid_until")
        remind_days = data.get("remind_days", DEFAULT_REMIND_DAYS)
        if (
            isinstance(remind_days, bool)
            or not isinstance(remind_days, int)
            or not 0 <= remind_days <= 365
        ):
            _bad("remind_days", "remind_days must be 0 to 365")

        adj = _get(member)
        created = adj is None
        if adj is None:
            adj = MemberFeeAdjustment(member_id=member.id, created_by_id=actor_id)
            db.session.add(adj)
        elif adj.valid_until != valid_until:
            # A new end date: ask again before it, and tell again when it ends.
            adj.reminder_sent_at = None
            adj.confirmed_at = None
            adj.confirmation_note = None
            adj.ended_notice_at = None
        adj.kind = kind
        adj.amount_chf = amount
        adj.percent = percent
        adj.reason = reason  # type: ignore[assignment]
        adj.valid_until = valid_until
        adj.remind_days = remind_days
        db.session.flush()
        # The reason can be personal: the audit log keeps only what changed.
        log_audit(
            actor_id,
            "set_fee_adjustment" if not created else "create_fee_adjustment",
            "Member",
            member.id,
            f"{member.name}: {kind}"
            + (f" until {valid_until:%d.%m.%Y}" if valid_until else ""),
        )
        db.session.expire(member, ["fee_adjustment"])
        return adj

    @staticmethod
    def remove(member: Member, actor_id: int) -> None:
        adj = _get(member)
        if adj is None:
            raise_error(404, "NOT_FOUND", "This member pays the standard fee")
        db.session.delete(adj)
        log_audit(actor_id, "delete_fee_adjustment", "Member", member.id, member.name)
        db.session.flush()
        db.session.expire(member, ["fee_adjustment"])

    @staticmethod
    def confirm(member: Member, data: dict) -> MemberFeeAdjustment:
        """The member says the reason for their fee still applies."""
        adj = _get(member)
        if adj is None:
            raise_error(404, "NOT_FOUND", "You pay the standard fee")
        if adj.valid_until is not None and adj.valid_until < date.today():
            raise_error(
                409,
                "FEE_ADJUSTMENT_ENDED",
                "This arrangement has ended; please contact the board",
            )
        note = _text(data.get("note"), "note", MAX_NOTE, required=True)
        adj.confirmed_at = datetime.now(timezone.utc)
        adj.confirmation_note = note
        log_audit(member.id, "confirm_fee_adjustment", "Member", member.id, member.name)
        from hubra.core.notifications.staff import notify_permitted

        notify_permitted(
            "tiers.fee_adjustments.update",
            "info",
            "Fee reason confirmed",
            member.name,
            skip_member_id=member.id,
            link=member_link(member.id),
        )
        db.session.flush()
        return adj

    @staticmethod
    def list_all() -> list[dict]:
        """Every member with their own fee, ending soonest first."""
        rows = db.session.scalars(
            select(MemberFeeAdjustment)
            .join(Member, Member.id == MemberFeeAdjustment.member_id)
            .where(Member.archived_at.is_(None))
            .options(selectinload(MemberFeeAdjustment.member))
        ).all()
        today = date.today()
        out = []
        for adj in rows:
            item = adjustment_to_dict(adj, today)
            item["member_name"] = adj.member.name
            out.append(item)
        out.sort(key=lambda a: (a["valid_until"] is None, a["valid_until"] or ""))
        return out
