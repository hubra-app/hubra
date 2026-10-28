"""PaymentPlan: how a membership tier can be paid (tenant schema).

A tier says what a member gets and what it costs per year; a plan says how
that is billed (yearly, half-yearly, quarterly, monthly), optionally with a
surcharge for paying in instalments. A member without a plan is billed on
the tier's own billing cycle.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vollbuild.core.extensions import db

PLAN_INTERVALS = ("yearly", "half_yearly", "quarterly", "monthly")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PaymentPlan(db.Model):
    __tablename__ = "payment_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    tier_id: Mapped[int] = mapped_column(
        db.Integer,
        ForeignKey("membership_tiers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(db.String(120), nullable=False)
    interval: Mapped[str] = mapped_column(db.String(20), nullable=False)
    # Added on top of the tier's annual fee, in percent (instalment surcharge).
    surcharge_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0")
    )
    # Members may pick visible plans themselves.
    visible: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    tier = relationship("MembershipTier", back_populates="payment_plans")
