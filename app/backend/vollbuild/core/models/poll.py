"""Poll, PollOption, and PollVote models."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vollbuild.core.extensions import db


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
        "PollOption", back_populates="poll", cascade="all, delete-orphan"
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
    member_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("members.id"), nullable=False
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
    member: Mapped["Member"] = relationship("Member")  # type: ignore[name-defined]  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<PollVote id={self.id} poll_id={self.poll_id} member_id={self.member_id}>"
        )
