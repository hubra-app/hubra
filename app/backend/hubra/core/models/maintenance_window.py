"""MaintenanceWindow: planned maintenance for every club or some of them.

Public schema only.  While a window runs, the clubs it covers get the same
503 and maintenance page as maintenance mode (``services.maintenance``); a
window for every club also pauses alerts like maintenance mode does.  From
``notice_hours`` before its start, the club app shows a notice with the
time and message.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


class MaintenanceWindow(db.Model):
    __tablename__ = "maintenance_windows"

    id: Mapped[int] = mapped_column(primary_key=True)
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    ends_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Club ids, or null for every club.  No foreign keys: a deleted club
    # must not take the record with it.
    tenant_ids: Mapped[list | None] = mapped_column(
        JSONB().with_variant(db.JSON, "sqlite"), nullable=True
    )
    notice_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
