"""Outgoing webhooks: a club's own tools hear about changes (docs/webhooks.md)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Webhook(db.Model):
    """An https address that gets a signed POST for the events it lists."""

    __tablename__ = "webhooks"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(100), nullable=False)
    url: Mapped[str] = mapped_column(db.String(500), nullable=False)
    # The signing secret, encrypted (hubra.core.crypto, purpose webhooks.secret).
    secret: Mapped[str] = mapped_column(Text, nullable=False)
    events: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    active: Mapped[bool] = mapped_column(db.Boolean, default=True, nullable=False)
    # Failed deliveries in a row; at MAX_FAILURES the hook switches itself off.
    failures: Mapped[int] = mapped_column(db.Integer, default=0, nullable=False)
    disabled_reason: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    last_delivery_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Webhook id={self.id} {self.name!r}>"


class WebhookDelivery(db.Model):
    """One event sent (or tried) to one webhook; the newest are kept."""

    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(primary_key=True)
    webhook_id: Mapped[int] = mapped_column(
        db.Integer,
        ForeignKey("webhooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The id the receiver sees (X-Hubra-Delivery), the same on every retry.
    uid: Mapped[str] = mapped_column(db.String(36), nullable=False, unique=True)
    event: Mapped[str] = mapped_column(db.String(64), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # pending | delivered | failed (no retry left)
    status: Mapped[str] = mapped_column(
        db.String(20), default="pending", nullable=False
    )
    attempts: Mapped[int] = mapped_column(db.Integer, default=0, nullable=False)
    response_status: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
