"""Binding model — links a source entity's attribute to an InternalKey.

When a source's attribute changes, the binding engine resolves the new value
and writes it (encrypted) into the referenced InternalKey via KeyService.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hubra.core.extensions import db


class Binding(db.Model):
    """A binding from a source attribute to an internal key.

    ``type`` identifies the source entity kind:
      member | group | function | setting | mail_address

    ``source_id`` is the source record's id (as a string — settings use
    string keys, other entities use str(int_id)).

    ``source_attribute`` is chosen from the per-type attribute registry.

    ``key_id`` FK references the target InternalKey.

    ``validator`` (none|email|url|non_empty) — optional validation.

    ``is_protected`` blocks delete AND enable/disable toggle; the key
    is immutable; source_id / source_attribute / validator stay editable.

    ``enabled`` controls whether the binding contributes its value.

    ``validation_status`` (ok|failed) tracks the last sync result.
    """

    __tablename__ = "bindings"
    __table_args__ = (
        UniqueConstraint(
            "key_id",
            "type",
            "source_id",
            "source_attribute",
            name="uq_binding_key_type_source_attr",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_attribute: Mapped[str] = mapped_column(String(100), nullable=False)
    key_id: Mapped[int] = mapped_column(
        db.Integer,
        ForeignKey("internal_keys.id", ondelete="CASCADE"),
        nullable=False,
    )
    validator: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    is_protected: Mapped[bool] = mapped_column(
        db.Boolean, default=False, nullable=False
    )
    enabled: Mapped[bool] = mapped_column(db.Boolean, default=True, nullable=False)
    validation_status: Mapped[str] = mapped_column(
        String(20), default="ok", nullable=False
    )
    validation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    key: Mapped["InternalKey"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "InternalKey", back_populates="bindings"
    )

    def __repr__(self) -> str:
        return (
            f"<Binding id={self.id} type={self.type!r} "
            f"source_id={self.source_id!r} attr={self.source_attribute!r}>"
        )
