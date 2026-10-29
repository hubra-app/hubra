"""Notification model — per-member in-app notifications."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hubra.core.extensions import db


class Notification(db.Model):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("members.id"), nullable=False, index=True
    )
    # info | success | warning | member
    kind: Mapped[str] = mapped_column(db.String(20), nullable=False)
    title: Mapped[str] = mapped_column(db.String(255), nullable=False)
    msg: Mapped[str] = mapped_column(db.String(255), nullable=False)
    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    read: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)

    # Relationships
    member: Mapped["Member"] = relationship("Member")  # type: ignore[name-defined]  # noqa: F821

    def __repr__(self) -> str:
        return f"<Notification id={self.id} kind={self.kind!r} read={self.read}>"
