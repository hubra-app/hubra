"""Finance models: TransactionCategory, Transaction, Invoice."""

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
    category_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("transaction_categories.id"), nullable=False
    )
    member_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("members.id"), nullable=True
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
    category: Mapped["TransactionCategory"] = relationship(
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
