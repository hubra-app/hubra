"""Club invites: the only way a club adds someone.

The account is the person's own (password, email, name and contact details,
shared with their other clubs), so a club never creates or changes one. It
sends a personal link instead; the person signs in, or signs up with the
invited address, on the SSO portal and accepts. Accepting happens without a
club selected, so the table lives in the public schema only (it is in no
module manifest and never cloned into a club schema).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


class ClubInvite(db.Model):
    __tablename__ = "club_invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    # The address the link was sent to; only the account with this address
    # can accept it.
    email: Mapped[str] = mapped_column(db.String(255), nullable=False, index=True)
    # SHA-256 hex digest of the raw token in the link.
    token_hash: Mapped[str] = mapped_column(db.String(64), unique=True, nullable=False)
    invited_by: Mapped[str] = mapped_column(db.String(255), nullable=False, default="")
    # What the club already decided for the new member (tier, groups, status,
    # membership type, notes); applied when the invite is accepted.
    member_data: Mapped[dict | None] = mapped_column(
        JSONB().with_variant(db.JSON, "sqlite"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    @property
    def is_open(self) -> bool:
        expires = self.expires_at
        # SQLite returns naive datetimes; treat them as UTC for comparison.
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return self.accepted_at is None and datetime.now(timezone.utc) < expires
