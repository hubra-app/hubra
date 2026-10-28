"""TenantRequest model — user-submitted requests for new tenant creation.

Stored in the public schema. Users submit requests; superadmins approve
or reject them. On approval, TenantService.provision_tenant() is called
and the requesting user is linked as the tenant admin.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


class TenantRequest(db.Model):
    __tablename__ = "tenant_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    slug: Mapped[str] = mapped_column(db.String(255), nullable=False, index=True)
    plan: Mapped[str] = mapped_column(db.String(50), nullable=False, default="starter")
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(
        db.Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_tenant_id: Mapped[int | None] = mapped_column(
        db.Integer,
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
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
        return f"<TenantRequest id={self.id} slug={self.slug!r} status={self.status!r}>"
