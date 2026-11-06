"""The contract outbox: plugin events and queued actions, kept until handled.

A row is written in the same transaction as the change that caused it, so
an event exists exactly when the change does (transactional outbox). The
transport (``hubra.core.contracts.transport``) hands it to a worker after
the commit; a sweep picks up whatever the transport lost. One public table
for every club (``tenant_id``), so one sweep and, later, one relay to a
message broker can read it.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db

_JSON = JSONB().with_variant(db.JSON, "sqlite")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ContractMessage(db.Model):
    """One delivery: an event to one subscriber, or one queued action."""

    __tablename__ = "contract_outbox"
    __table_args__ = (Index("ix_contract_outbox_due", "status", "next_attempt_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # This delivery; the same on every retry.
    uid: Mapped[str] = mapped_column(db.String(36), nullable=False, unique=True)
    # The event or command (the envelope's id): shared by the deliveries
    # of one event to several subscribers.
    message_id: Mapped[str] = mapped_column(db.String(36), nullable=False, index=True)
    # event | action | job (a Celery task queued after the commit)
    kind: Mapped[str] = mapped_column(db.String(10), nullable=False)
    name: Mapped[str] = mapped_column(db.String(120), nullable=False)
    # The module that handles it, and for an event its handler.
    module_code: Mapped[str] = mapped_column(db.String(100), nullable=False)
    target: Mapped[str] = mapped_column(db.String(255), nullable=False, default="")
    tenant_id: Mapped[int | None] = mapped_column(db.Integer, nullable=True)
    # The envelope (hubra.core.contracts.transport.envelope).
    envelope: Mapped[dict] = mapped_column(_JSON, nullable=False)
    # pending | done | dead (no retry left, or one that can't succeed)
    status: Mapped[str] = mapped_column(
        db.String(10), nullable=False, default="pending"
    )
    attempts: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    done_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<ContractMessage {self.kind} {self.name} -> {self.module_code} {self.status}>"
