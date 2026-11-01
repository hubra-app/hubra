"""PlatformEvent: the platform's own event log, in the public schema.

One row per thing that happened to the instance rather than to a club's
data: every mail handed to the relay (sent, sent through the fallback,
failed), relay checks that changed state, system alerts (Redis, database,
disk, failing tasks) and the alert mails sent to platform staff.  People's
actions stay in ``global_audit_logs``; this is the monitoring side.

Shown in manage › Diagnostics › Event log, kept for ``RETENTION_DAYS``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db

CATEGORIES = ("mail", "relay", "system", "alert")
LEVELS = ("info", "warning", "error")


class PlatformEvent(db.Model):
    __tablename__ = "platform_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(10), nullable=False, default="info")
    # The club the event belongs to (a club's mail), if any.  No foreign key:
    # the log outlives a deleted club, and writing it must never fail on one.
    tenant_id: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column(
        JSONB().with_variant(db.JSON, "sqlite"), nullable=True
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "time": self.created_at.isoformat() if self.created_at else None,
            "category": self.category,
            "kind": self.kind,
            "level": self.level,
            "tenant_id": self.tenant_id,
            "message": self.message,
            "details": self.details or {},
        }
