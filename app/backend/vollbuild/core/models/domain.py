"""Domain model — maps custom domains to tenants with DNS verification."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from vollbuild.core.extensions import db

_VERIFICATION_PREFIX = "verevia-verify="


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
