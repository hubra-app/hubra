"""InternalKey model — encrypted key-value store for binding-managed values.

These are backend-only: NOT settings, and never appear in the settings list,
the settings API, or config export. Access is exclusively via KeyService.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hubra.core.extensions import db


class InternalKey(db.Model):
    """A key whose value is written by the binding engine.

    ``value`` is ALWAYS encrypted at rest (Fernet / SECRET_KEY).
    A scalar key (``allow_multiple=False``) holds ONE binding's value.
    An array key (``allow_multiple=True``) holds MANY bindings' values
    as a JSON array (deduped, stable-ordered).
    """

    __tablename__ = "internal_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    allow_multiple: Mapped[bool] = mapped_column(
        db.Boolean, default=False, nullable=False
    )
    is_protected: Mapped[bool] = mapped_column(
        db.Boolean, default=False, nullable=False
    )
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
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

    bindings: Mapped[list["Binding"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Binding",
        back_populates="key",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<InternalKey id={self.id} key={self.key!r}>"
