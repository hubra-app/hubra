"""Mail models — MailboxFolder only.

All mailbox/alias/log tracking is handled by MailboxFolder (IMAP folder
counts synced from WildDuck) and ManagedMailAddress (protected club
addresses). The legacy Mailbox, Alias, AliasRecipient, MailLogEntry, and
MailLogLine models have been removed.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vollbuild.core.extensions import db

if TYPE_CHECKING:
    from vollbuild.core.models.member import Member


class MailboxFolder(db.Model):
    """A WildDuck IMAP folder (INBOX, Sent, ...) with synced message counters.

    Populated by the ``sync_wildduck_message_counts`` Celery beat task.
    One member can have multiple folders; each maps to a WildDuck
    ``mailbox`` object (the IMAP sense, not the SMTP identity sense).
    """

    __tablename__ = "mailbox_folders"

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("members.id"), nullable=False
    )
    wildduck_mailbox_id: Mapped[str] = mapped_column(db.String(255), nullable=False)
    path: Mapped[str] = mapped_column(db.String(255), nullable=False)
    message_count: Mapped[int] = mapped_column(db.Integer, default=0, nullable=False)
    unread_count: Mapped[int] = mapped_column(db.Integer, default=0, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (UniqueConstraint("member_id", "wildduck_mailbox_id"),)

    member: Mapped["Member"] = relationship("Member", back_populates="mailbox_folders")

    def __repr__(self) -> str:
        return (
            f"<MailboxFolder id={self.id} member_id={self.member_id}"
            f" path={self.path!r}>"
        )

    @staticmethod
    def total_message_count(member_id: int) -> int:
        return (
            db.session.scalar(
                select(func.coalesce(func.sum(MailboxFolder.message_count), 0)).where(
                    MailboxFolder.member_id == member_id
                )
            )
            or 0
        )
