from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from vollbuild.extensions import db


class QrrReference(db.Model):
    __tablename__ = "qrr_references"
    __table_args__ = (UniqueConstraint("opaque_reference", name="uq_qrr_opaque_ref"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    opaque_reference: Mapped[str] = mapped_column(
        String(27), nullable=False, index=True
    )
    member_id: Mapped[int] = mapped_column(Integer, nullable=False)
    invoice_id: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<QrrReference id={self.id} "
            f"opaque={self.opaque_reference!r} "
            f"member_id={self.member_id} invoice_id={self.invoice_id}>"
        )
