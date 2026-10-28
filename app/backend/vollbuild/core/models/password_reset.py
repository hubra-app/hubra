"""Password reset token model — single-use, time-limited tokens.

Tokens reference the global User (not the tenant-scoped Member) because
passwords are now global. The token table itself remains per-tenant
(cloned into every tenant schema) so that each tenant has its own reset token store,
but the FK points to the public.users table.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vollbuild.core.extensions import db


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # SHA-256 hex digest of the raw token sent in the reset email.
    token_hash: Mapped[str] = mapped_column(db.String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User")  # type: ignore[name-defined]  # noqa: F821

    @property
    def is_valid(self) -> bool:
        now = datetime.now(timezone.utc)
        expires = self.expires_at
        # SQLite returns naive datetimes; treat them as UTC for comparison.
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return not self.used and now < expires

    def __repr__(self) -> str:
        return (
            f"<PasswordResetToken id={self.id} user_id={self.user_id} used={self.used}>"
        )
