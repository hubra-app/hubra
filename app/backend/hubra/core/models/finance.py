"""Finance models: TransactionCategory, Transaction, RecurringTransaction, Invoice."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hubra.core.extensions import db


class TransactionCategory(db.Model):
    __tablename__ = "transaction_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(255), unique=True, nullable=False)
    color: Mapped[str | None] = mapped_column(db.String(7), nullable=True)
    is_default: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)

    # Relationships
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="category"
    )

    def __repr__(self) -> str:
        return f"<TransactionCategory id={self.id} name={self.name!r}>"


class Transaction(db.Model):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(db.String(255), nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("transaction_categories.id"), nullable=True
    )
    member_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("members.id"), nullable=True
    )
    # The recurring transaction that booked this one, if any.
    recurring_id: Mapped[int | None] = mapped_column(
        db.Integer,
        ForeignKey("recurring_transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payee_name: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # IBAN | Card | Twint | Cash
    method: Mapped[str] = mapped_column(db.String(50), nullable=False)
    # income | expense
    type: Mapped[str] = mapped_column(db.String(20), nullable=False)
    # Pending | Completed
    status: Mapped[str] = mapped_column(
        db.String(20), default="Completed", nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    category: Mapped["TransactionCategory | None"] = relationship(
        "TransactionCategory", back_populates="transactions"
    )
    member: Mapped["Member | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member"
    )
    # Back-reference: the invoice that spawned this transaction (if any)
    invoice: Mapped["Invoice | None"] = relationship(
        "Invoice",
        back_populates="transaction",
        foreign_keys="[Invoice.transaction_id]",
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"<Transaction id={self.id} amount={self.amount} type={self.type!r}>"


RECURRING_INTERVALS = ("monthly", "quarterly", "half_yearly", "yearly")


class RecurringTransaction(db.Model):
    """An income or expense that repeats (rent, insurance, league fees).

    A daily job books a Transaction on each due date and moves next_date on.
    """

    __tablename__ = "recurring_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    description: Mapped[str] = mapped_column(db.String(255), nullable=False)
    # income | expense, as on Transaction; amount is always positive here.
    type: Mapped[str] = mapped_column(db.String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        db.Integer,
        ForeignKey("transaction_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    payee_name: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    method: Mapped[str] = mapped_column(db.String(50), nullable=False)
    interval: Mapped[str] = mapped_column(db.String(20), nullable=False)
    # Each booking falls on start_date plus whole intervals.
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # The next date to book; None once the end date has passed.
    next_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    # Booked as Completed (a standing order) instead of Pending (to confirm).
    book_completed: Mapped[bool] = mapped_column(
        db.Boolean, default=False, nullable=False
    )
    # Part of the club's yearly expenses that membership fees are based on.
    counts_for_fees: Mapped[bool] = mapped_column(
        db.Boolean, default=True, nullable=False
    )
    active: Mapped[bool] = mapped_column(db.Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    category: Mapped["TransactionCategory | None"] = relationship(
        "TransactionCategory"
    )

    def __repr__(self) -> str:
        return (
            f"<RecurringTransaction id={self.id} amount={self.amount} "
            f"interval={self.interval!r}>"
        )


class Invoice(db.Model):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("members.id"), nullable=True, index=True
    )
    external_party_id: Mapped[int | None] = mapped_column(
        db.Integer,
        ForeignKey("external_parties.id", ondelete="SET NULL"),
        nullable=True,
    )
    transaction_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True
    )
    issued: Mapped[date] = mapped_column(Date, nullable=False)
    due: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(db.String(20), default="Open", nullable=False)
    # 'membership' | 'other' — drives amount derivation and linked tx category.
    # 'membership' requires a member recipient; 'other' allows custom amount/category.
    purpose: Mapped[str] = mapped_column(
        db.String(20), default="membership", nullable=False
    )
    description: Mapped[str | None] = mapped_column(db.String(512), nullable=True)
    # What a membership invoice covers: from the first day billed (a later
    # one for a member who joined during the period) to the period's end.
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    member: Mapped["Member | None"] = relationship("Member")  # type: ignore[name-defined]  # noqa: F821
    external_party: Mapped["ExternalParty | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "ExternalParty", back_populates="invoices"
    )
    transaction: Mapped["Transaction | None"] = relationship(
        "Transaction",
        back_populates="invoice",
        foreign_keys=[transaction_id],
    )

    def __repr__(self) -> str:
        return (
            f"<Invoice id={self.id} member_id={self.member_id} "
            f"external_party_id={self.external_party_id} status={self.status!r}>"
        )
