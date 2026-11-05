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

    Private until shared; a shared one shows in everyone's dashboard tabs,
    and each viewer sees only the widgets their permissions allow.
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
