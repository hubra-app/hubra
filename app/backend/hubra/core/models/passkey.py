"""Passkeys (WebAuthn credentials) an account signs in with.

Public schema only: the table is in no module manifest.  See
hubra/api/auth/passkeys.py.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


class Passkey(db.Model):
    __tablename__ = "passkeys"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        db.Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # base64url of the authenticator's credential id.
    credential_id: Mapped[str] = mapped_column(
        db.String(1400), nullable=False, unique=True
    )
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sign_count: Mapped[int] = mapped_column(db.Integer, default=0, nullable=False)
    transports: Mapped[str | None] = mapped_column(db.String(200), nullable=True)
    # A name the person gives it, e.g. "iPhone" or "YubiKey".
    name: Mapped[str] = mapped_column(db.String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Passkey id={self.id} user_id={self.user_id}>"
