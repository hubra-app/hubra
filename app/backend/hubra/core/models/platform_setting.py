"""PlatformSetting: instance-wide settings in the public schema.

One row per key, for the whole platform rather than one club: the outbound
mail relay and the sender of system mail (sign-in, SSO, platform notices).
Not listed in any module manifest, so club schemas never get a copy.
Secret values are encrypted at rest like ``InternalKey``.  Access goes
through ``hubra.core.services.platform_settings``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


class PlatformSetting(db.Model):
    __tablename__ = "platform_settings"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_by: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<PlatformSetting {self.key}>"
