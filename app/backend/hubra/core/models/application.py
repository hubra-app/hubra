"""Application model — prospective member applications."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hubra.core.extensions import db


class Application(db.Model):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    email: Mapped[str] = mapped_column(db.String(255), unique=True, nullable=False)
    wants_tier_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("membership_tiers.id"), nullable=True
    )
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    avatar_color: Mapped[str | None] = mapped_column(db.String(7), nullable=True)

    # Relationships
    wants_tier: Mapped["MembershipTier | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "MembershipTier", back_populates="applications"
    )

    def __repr__(self) -> str:
        return f"<Application id={self.id}>"
