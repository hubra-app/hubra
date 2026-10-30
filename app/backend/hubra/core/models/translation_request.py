"""TranslationRequest — a club's suggestion for a platform text.

Stored in the public schema. The texts are the platform's alone: a club
suggests a new wording, and a platform admin accepts it (the text changes for
every club) or rejects it with a note.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


class TranslationRequest(db.Model):
    __tablename__ = "translation_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    locale: Mapped[str] = mapped_column(String(10), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    # The text when the suggestion was made, so the admin sees what changes.
    current_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_value: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # pending | accepted | rejected
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def to_dict(self, tenant_name: str | None = None) -> dict:
        return {
            "id": self.id,
            "tenantId": self.tenant_id,
            "tenantName": tenant_name,
            "locale": self.locale,
            "key": self.key,
            "currentValue": self.current_value,
            "proposedValue": self.proposed_value,
            "note": self.note,
            "status": self.status,
            "decisionNote": self.decision_note,
            "decidedAt": self.decided_at.isoformat() if self.decided_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
