"""DataRequest: someone asks a club for their personal data or for it to be
deleted (GDPR art. 15/17, Swiss nDSG art. 25/32), and when manage handled it.

Public schema only, with no foreign keys: the record of what was asked and
done has to outlive the member and even the club.  It keeps only what is
needed to show the request was handled: who asked (name and address), what
for, when it came in, the deadline, and who handled it when, with what
result.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


class DataRequest(db.Model):
    __tablename__ = "data_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    tenant_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # "export" (a copy of their data) or "deletion".
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    # "open", "done" or "rejected".
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="open", index=True
    )
    subject_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    subject_email: Mapped[str] = mapped_column(String(320), nullable=False, default="")
    # The person's member id in that club, once known.
    member_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    received_on: Mapped[date] = mapped_column(Date, nullable=False)
    # How it came in: mail, letter, the club, ...
    received_via: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    due_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    handled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    handled_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # What was done: rows per table for an export, what went for a deletion.
    result: Mapped[dict | None] = mapped_column(
        JSONB().with_variant(db.JSON, "sqlite"), nullable=True
    )
    # Each download of the export: [{"at": iso, "by": user id}].
    exports: Mapped[list | None] = mapped_column(
        JSONB().with_variant(db.JSON, "sqlite"), nullable=True
    )
