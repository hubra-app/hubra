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
    # Where the person came from: the tag of a join poster's QR code
    # (hubra.core.services.signup_source).
    source: Mapped[str | None] = mapped_column(db.String(40), nullable=True)

    # Relationships
    wants_tier: Mapped["MembershipTier | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "MembershipTier", back_populates="applications"
    )

    def __repr__(self) -> str:
        return f"<Application id={self.id}>"


class SignupSource(db.Model):
    """One request to join or trial booking that came with a source tag (a
    poster's QR code). No one's details: only what and when, so the club
    still sees which poster worked after the request is decided."""

    __tablename__ = "signup_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    # "join" or "trial"
    kind: Mapped[str] = mapped_column(db.String(10), nullable=False)
    source: Mapped[str] = mapped_column(db.String(40), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<SignupSource {self.kind} {self.source!r}>"
