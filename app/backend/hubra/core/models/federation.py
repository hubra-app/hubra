"""Federation links: an umbrella association and its member clubs.

An association (a club with the ``federation`` module on) invites a club by
its address; the club's admins accept in their own settings and choose
whether the association may see the contacts of their functions. Both clubs
are tenants, so the link lives in the public schema only (it is in no module
manifest and never cloned into a club schema).
"""

from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db

LINK_STATUSES = ("invited", "active")


class FederationLink(db.Model):
    __tablename__ = "federation_links"
    __table_args__ = (UniqueConstraint("federation_id", "club_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # The association.
    federation_id: Mapped[int] = mapped_column(
        db.Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The member club.
    club_id: Mapped[int] = mapped_column(
        db.Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="invited")
    # Chosen by the member club: the association sees who holds the club's
    # functions, with the function's mail address or the holder's club address.
    share_contacts: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa.text("false")
    )
    invited_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<FederationLink {self.federation_id}->{self.club_id} {self.status}>"
