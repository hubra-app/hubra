"""Sign-ins to the account itself (SSO portal, manager portal).

A club sign-in is a Session row in that club's schema, tied to the Member.
Signing in on the SSO portal opens no club, so there is no Member to tie it
to: those sign-ins are recorded here, once per browser, in the public schema
only (the table is in no module manifest and never cloned into a club
schema).  The tokens carry the row's id as ``account_sid``; a club switch
keeps it, so ending this sign-in also ends the club tokens it led to.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


class AccountSession(db.Model):
    __tablename__ = "account_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        db.Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Browser family + platform, as for club Devices (no version numbers).
    fingerprint: Mapped[str] = mapped_column(db.String(64), nullable=False)
    browser_family: Mapped[str | None] = mapped_column(db.String(50), nullable=True)
    platform: Mapped[str | None] = mapped_column(db.String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(db.String(512), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(db.String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_reason: Mapped[str | None] = mapped_column(db.String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<AccountSession id={self.id} user_id={self.user_id}>"
