from __future__ import annotations

import logging
from datetime import datetime, timezone

from cryptography.fernet import InvalidToken
from sqlalchemy import Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hubra.core.crypto import decrypt_code
from hubra.core.extensions import db


class Code(db.Model):
    __tablename__ = "codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("members.id"), nullable=True
    )
    updated_by_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("members.id"), nullable=True
    )
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

    created_by: Mapped["Member | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member", foreign_keys=[created_by_id]
    )
    updated_by: Mapped["Member | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member", foreign_keys=[updated_by_id]
    )

    @property
    def plain_code(self) -> str:
        """The code in clear text, or "" when it no longer decrypts (the
        encryption key changed), so one bad row does not break the list."""
        try:
            return decrypt_code(self.code, "codes.code")
        except InvalidToken:
            logging.getLogger(__name__).warning(
                "Code %s cannot be decrypted; wrong club, or its key is missing from FERNET_OLD_KEYS?",
                self.id,
            )
            return ""

    def __repr__(self) -> str:
        return f"<Code id={self.id} name={self.name!r}>"
