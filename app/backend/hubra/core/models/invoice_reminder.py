"""InvoiceReminderHistory model — tracks all invoice-related email dispatches."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hubra.core.extensions import db


class InvoiceReminderHistory(db.Model):
    __tablename__ = "invoice_reminder_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("invoices.id"), nullable=False
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    reminder_type: Mapped[str] = mapped_column(db.String(50), nullable=False)
    recipient_email: Mapped[str] = mapped_column(db.String(255), nullable=False)
    recipient_name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    success: Mapped[bool] = mapped_column(db.Boolean, default=True, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    invoice: Mapped["Invoice"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Invoice"
    )

    def __repr__(self) -> str:
        return (
            f"<InvoiceReminderHistory id={self.id} invoice_id={self.invoice_id} "
            f"type={self.reminder_type!r}>"
        )
