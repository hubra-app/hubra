"""SupportAccessRequest: Hubra staff asking a club to let them in.

A club with the setting ``support_requires_approval`` on must approve a
support session first (club app › Settings › Club). Platform table: the
request is made from manage and checked when the session starts.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


class SupportAccessRequest(db.Model):
    __tablename__ = "support_access_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The staff member who asks; only they may use the approval.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    minutes: Mapped[int] = mapped_column(nullable=False)
    allow_changes: Mapped[bool] = mapped_column(nullable=False, default=False)
    # pending | approved | declined | used
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    decided_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
