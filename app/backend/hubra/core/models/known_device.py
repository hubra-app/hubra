"""Browsers an account has signed in from, for the new-device sign-in mail.

Each browser gets a random token in a long-lived cookie (``hubra_device``);
only its hash is stored here, once per account that signs in with it.  A
sign-in without a known token is from a new device.  Public schema only,
like ``account_sessions``: the table is in no module manifest.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


class KnownDevice(db.Model):
    __tablename__ = "known_devices"
    __table_args__ = (UniqueConstraint("user_id", "token_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        db.Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # SHA-256 of the cookie token, never the token itself.
    token_hash: Mapped[str] = mapped_column(db.String(64), nullable=False)
    browser_family: Mapped[str | None] = mapped_column(db.String(50), nullable=True)
    platform: Mapped[str | None] = mapped_column(db.String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<KnownDevice id={self.id} user_id={self.user_id}>"
