"""ExternalParty model — non-member invoice recipients."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vollbuild.core.extensions import db


class ExternalParty(db.Model):
    __tablename__ = "external_parties"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_house_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address_postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address_city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_country: Mapped[str] = mapped_column(
        String(2), default="CH", nullable=False
    )
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)

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
    invoices: Mapped[list["Invoice"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Invoice", back_populates="external_party"
    )

    def __repr__(self) -> str:
        return f"<ExternalParty id={self.id} name={self.name!r}>"
