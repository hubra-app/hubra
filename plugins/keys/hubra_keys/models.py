"""Key and KeyHandover models (tenant schema)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hubra.core.extensions import db

KEY_KINDS = ("key", "card", "fob")
KEY_STATUSES = ("available", "issued", "lost", "retired")
HANDOVER_ACTIONS = ("issue", "return", "lost", "found", "retire")


class Key(db.Model):
    __tablename__ = "keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(db.String(120), nullable=False)
    # Engraved or printed number, unique per club when set.
    number: Mapped[str | None] = mapped_column(
        db.String(100), nullable=True, unique=True
    )
    kind: Mapped[str] = mapped_column(db.String(20), nullable=False, default="key")
    # Free text: which doors, lockers or rooms it opens.
    opens: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        db.String(20), nullable=False, default="available"
    )
    holder_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    deposit_chf: Mapped[float | None] = mapped_column(db.Numeric(10, 2), nullable=True)
    # A combination or door code stored encrypted in the codes module.
    code_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("codes.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    holder: Mapped["Member | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member", foreign_keys=[holder_id]
    )
    handovers: Mapped[list["KeyHandover"]] = relationship(
        "KeyHandover",
        back_populates="key",
        cascade="all, delete-orphan",
        order_by="KeyHandover.at.desc()",
    )

    def __repr__(self) -> str:
        return f"<Key id={self.id} label={self.label!r} status={self.status}>"


class KeyHandover(db.Model):
    """One entry in a key's history: issued, returned, lost, found, retired."""

    __tablename__ = "key_handovers"

    id: Mapped[int] = mapped_column(primary_key=True)
    key_id: Mapped[int] = mapped_column(
        db.Integer,
        ForeignKey("keys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(db.String(20), nullable=False)
    # Who received or gave back the key.
    member_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    # Who recorded it.
    by_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    key: Mapped["Key"] = relationship("Key", back_populates="handovers")
    member: Mapped["Member | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member", foreign_keys=[member_id]
    )
    by: Mapped["Member | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member", foreign_keys=[by_id]
    )
