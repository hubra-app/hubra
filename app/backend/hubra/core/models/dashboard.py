"""Dashboards a member puts together from widgets (docs/dashboards.md)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Dashboard(db.Model):
    """A member's own dashboard: a name and a list of widgets.

    Private until shared; a shared one shows in the dashboard tabs of the
    whole club, or only of the members of ``group_ids`` when set, and each
    viewer sees only the widgets their permissions allow. A row with
    ``home`` set holds a changed start page instead.
    """

    __tablename__ = "dashboards"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(100), nullable=False)
    owner_id: Mapped[int] = mapped_column(
        db.Integer,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shared: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)
    # Shared with these groups only (ids); None or [] = the whole club.
    group_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # A start page instead of a dashboard tab: "club" (Dashboard › Verein,
    # one per club, owner = whoever changed it last) or "me" (Dashboard ›
    # Persönlich, one per member). None for an ordinary dashboard.
    home: Mapped[str | None] = mapped_column(db.String(10), nullable=True)
    # [{"id": "w1", "type": "events.upcoming", "size": "m", "config": {...}}]
    widgets: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    owner = db.relationship("Member", foreign_keys=[owner_id])

    def __repr__(self) -> str:
        return f"<Dashboard id={self.id} name={self.name!r}>"
