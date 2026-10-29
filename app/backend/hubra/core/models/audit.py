"""AuditEntry model — immutable record of admin/system actions."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from hubra.core.extensions import db


class AuditEntry(db.Model):
    __tablename__ = "audit_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Nullable: system actions have no human actor
    actor_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("members.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(db.String(255), nullable=False)
    # e.g. "Member", "Invoice"
    target_type: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    target_id: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    target_label: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    actor_name: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    actor_avatar_color: Mapped[str | None] = mapped_column(db.String(50), nullable=True)
    color: Mapped[str | None] = mapped_column(db.String(50), nullable=True)
    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    actor: Mapped["Member | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member", foreign_keys=[actor_id]
    )

    @validates("actor_name", "target_label")
    def _fit_column(self, _key: str, value: str | None) -> str | None:
        # Two 255-character names make a 511-character actor name; the
        # entry must not fail (and roll back) the change it records.
        if value is not None and len(value) > 255:
            return value[:254] + "…"
        return value

    def __repr__(self) -> str:
        return f"<AuditEntry id={self.id} action={self.action!r}>"
