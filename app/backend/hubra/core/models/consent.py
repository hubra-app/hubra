"""MemberConsent: the log of a member's privacy choices (revDSG / GDPR).

One row per change, written when the member (or the board for them) changes
a consent: photos (``members.photo_consent``) or what they show in the
directory (``members.directory_shared``). The current value lives on the
member; this table answers "since when, and who changed it". It belongs to
the member and goes with them when they are deleted.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db

# What a member can consent to.
CONSENT_KINDS = ("photos", "directory")


class MemberConsent(db.Model):
    __tablename__ = "member_consents"

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # "photos" or "directory".
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    # The new value: true/false for photos, the shared fields for directory.
    value: Mapped[object] = mapped_column(
        JSONB().with_variant(db.JSON, "sqlite"), nullable=True
    )
    # Member id of who changed it (the member themselves, or the board).
    changed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # "self" (Account › Membership) or "board" (member form).
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="self")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
