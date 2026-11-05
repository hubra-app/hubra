"""Domain model — maps custom domains to tenants with DNS verification."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


class Domain(db.Model):
    __tablename__ = "domains"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    domain: Mapped[str] = mapped_column(db.String(255), unique=True, nullable=False)
    verified: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)
    verification_token: Mapped[str | None] = mapped_column(db.String(64), nullable=True)
    verification_status: Mapped[str] = mapped_column(
        db.String(20), default="pending", nullable=False
    )
    is_primary: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # When the TXT record was last looked up, and last found.
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Serving visitors (hubra.core.services.domain_serving): None (not
    # verified / never tried), off (switched off on the platform), pending
    # (certificate being issued), ready (Ingress in place), failed (no
    # certificate after a day).
    serving_status: Mapped[str | None] = mapped_column(db.String(20), nullable=True)
    serving_error: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
    serving_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    serving_since: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    serving_alerted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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

    def __repr__(self) -> str:
        return f"<Domain id={self.id} domain={self.domain!r} verified={self.verified}>"
