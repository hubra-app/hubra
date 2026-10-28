"""ItemGuide: the usage guide of one inventory item (tenant schema)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


class ItemGuide(db.Model):
    __tablename__ = "item_guides"

    # One guide per item; it goes when the item is deleted for good.
    item_id: Mapped[int] = mapped_column(
        db.Integer,
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # Markdown and/or a link to a manual or video.
    guide: Mapped[str | None] = mapped_column(Text, nullable=True)
    guide_url: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
