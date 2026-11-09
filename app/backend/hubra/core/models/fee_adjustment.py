"""MemberFeeAdjustment: a member's own membership fee (tenant schema).

Some members pay less than their tier says, or nothing: a student, someone
out of work, a family member. The board records why (``reason``), and may
set an end date. Before that date the member is asked to confirm that the
reason still applies; after it the member pays the tier's fee again.

One row per member. Kinds:
  - ``exempt``:  no membership fee
  - ``amount``:  their own yearly fee in CHF (split into their billing periods)
  - ``percent``: the tier's fee reduced by ``percent`` per cent
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hubra.core.extensions import db

FEE_ADJUSTMENT_KINDS = ("exempt", "amount", "percent")
# Days before the end date the member is asked to confirm the reason.
DEFAULT_REMIND_DAYS = 30
# Where members see and confirm their fee.
MY_FEE_LINK = "/app/account/settings/membership"


def member_link(member_id: int) -> str:
    """The member's page, where the board sets their fee."""
    return f"/app/members/{member_id}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MemberFeeAdjustment(db.Model):
    __tablename__ = "member_fee_adjustments"

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(
        db.Integer,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    kind: Mapped[str] = mapped_column(db.String(20), nullable=False)
    # Yearly fee in CHF, for kind "amount".
    amount_chf: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    # Reduction in per cent, for kind "percent".
    percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    # Last day the adjustment applies; None: until the board removes it.
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    remind_days: Mapped[int] = mapped_column(
        db.Integer, nullable=False, default=DEFAULT_REMIND_DAYS
    )
    # The member was asked to confirm the reason (once per end date).
    reminder_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # The member said the reason still applies, with their note.
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confirmation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The member and the board were told that it ended.
    ended_notice_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    member = relationship("Member", foreign_keys=[member_id])

    def active_on(self, day: date) -> bool:
        """Whether the adjustment applies to a billing period starting *day*."""
        return self.valid_until is None or day <= self.valid_until
