"""Poll, PollOption, and PollVote models."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, UniqueConstraint
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hubra.core.extensions import db


class Poll(db.Model):
    __tablename__ = "polls"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_by_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("members.id"), nullable=True
    )
    question: Mapped[str] = mapped_column(db.String(255), nullable=False)
    closes_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # open | closed
    status: Mapped[str] = mapped_column(db.String(20), default="open", nullable=False)
    is_required: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)
    required_group_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    required_function_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    # Proxy voting (general assembly): a member may let another member vote
    # for them, if the statutes allow it.
    allow_proxy: Mapped[bool] = mapped_column(
        db.Boolean, default=False, server_default=sa.false(), nullable=False
    )
    max_proxies_per_member: Mapped[int] = mapped_column(
        db.Integer, default=1, server_default="1", nullable=False
    )
    # When the reminder before closing went out; cleared when closes_at
    # changes.
    reminder_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    created_by: Mapped["Member | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member", foreign_keys=[created_by_id]
    )
    options: Mapped[list["PollOption"]] = relationship(
        "PollOption",
        back_populates="poll",
        cascade="all, delete-orphan",
        order_by="PollOption.id",
    )
    votes: Mapped[list["PollVote"]] = relationship(
        "PollVote", back_populates="poll", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Poll id={self.id} question={self.question!r:.40}>"


class PollOption(db.Model):
    __tablename__ = "poll_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    poll_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("polls.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(db.String(255), nullable=False)

    # Relationships
    poll: Mapped["Poll"] = relationship("Poll", back_populates="options")
    poll_votes: Mapped[list["PollVote"]] = relationship(
        "PollVote", back_populates="option", cascade="all, delete-orphan"
    )

    @property
    def vote_count(self) -> int:
        return len(self.poll_votes)

    def __repr__(self) -> str:
        return f"<PollOption id={self.id} label={self.label!r}>"


class PollVote(db.Model):
    __tablename__ = "poll_votes"
    __table_args__ = (
        UniqueConstraint("poll_id", "member_id", name="uq_poll_vote_member"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    poll_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("polls.id"), nullable=False
    )
    option_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("poll_options.id"), nullable=False
    )
    # None once the member is permanently deleted: the vote stays, anonymous,
    # so a decided poll's result does not change afterwards.
    member_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    # Set when a proxy holder cast this vote for ``member_id``.
    cast_by_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    cast_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    poll: Mapped["Poll"] = relationship("Poll", back_populates="votes")
    option: Mapped["PollOption"] = relationship(
        "PollOption", back_populates="poll_votes"
    )
    member: Mapped["Member"] = relationship("Member", foreign_keys=[member_id])  # type: ignore[name-defined]  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<PollVote id={self.id} poll_id={self.poll_id} member_id={self.member_id}>"
        )


class PollProxy(db.Model):
    """``grantor`` lets ``holder`` vote for them in one poll."""

    __tablename__ = "poll_proxies"
    __table_args__ = (
        UniqueConstraint("poll_id", "grantor_id", name="uq_poll_proxy_grantor"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    poll_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("polls.id", ondelete="CASCADE"), nullable=False
    )
    grantor_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    holder_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    grantor = relationship("Member", foreign_keys=[grantor_id])
    holder = relationship("Member", foreign_keys=[holder_id])
