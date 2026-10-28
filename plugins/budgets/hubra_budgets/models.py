"""Budget and BudgetLine models (tenant schema)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hubra.core.extensions import db

LINE_KINDS = ("income", "expense")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Budget(db.Model):
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("year", "name", name="uq_budget_year_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    year: Mapped[int] = mapped_column(db.Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(db.String(120), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Approved by the general assembly; approved budgets are read-only.
    approved: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    lines: Mapped[list[BudgetLine]] = relationship(
        back_populates="budget",
        cascade="all, delete-orphan",
        order_by="BudgetLine.id",
    )


class BudgetLine(db.Model):
    __tablename__ = "budget_lines"
    __table_args__ = (
        UniqueConstraint(
            "budget_id", "category_id", "kind", name="uq_budget_line_category"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    budget_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[int] = mapped_column(
        db.Integer,
        ForeignKey("transaction_categories.id", ondelete="CASCADE"),
        nullable=False,
    )
    # income | expense, matching Transaction.type
    kind: Mapped[str] = mapped_column(db.String(20), nullable=False)
    planned: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    note: Mapped[str | None] = mapped_column(db.String(255), nullable=True)

    budget: Mapped[Budget] = relationship(back_populates="lines")
    category = relationship("TransactionCategory")
