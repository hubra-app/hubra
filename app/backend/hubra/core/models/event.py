"""ClubEvent model, EventRegistration model, and event_attendees association table."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hubra.core.extensions import db

# ── Association table (kept for backward compat) ──────────────────────────────

event_attendees = Table(
    "event_attendees",
    db.metadata,
    Column(
        "event_id",
        db.Integer,
        ForeignKey("club_events.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "member_id",
        db.Integer,
        ForeignKey("members.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


# ── ClubEvent ─────────────────────────────────────────────────────────────────


class ClubEvent(db.Model):
    __tablename__ = "club_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(db.String(255), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    # e.g. "14:00-18:00"
    time: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    # Workshop | Social | Certification | Meeting
    type: Mapped[str] = mapped_column(db.String(50), nullable=False)

    # M5 new fields
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    meeting_url: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    all_day: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)
    # general | training | social | meeting | competition
    category: Mapped[str] = mapped_column(
        db.String(50), default="general", nullable=False
    )
    max_attendees: Mapped[int | None] = mapped_column(Integer, nullable=True)
    registration_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancellation_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    requires_approval: Mapped[bool] = mapped_column(
        db.Boolean, default=False, nullable=False
    )
    is_public: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)
    cover_image_url: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
    color: Mapped[str | None] = mapped_column(db.String(7), nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    # When the reminder before the start went out; cleared when the event
    # moves, so the new time gets one.
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
    attendees: Mapped[list["Member"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member",
        secondary=event_attendees,
        back_populates="events",
    )
    registrations: Mapped[list["EventRegistration"]] = relationship(
        "EventRegistration",
        back_populates="event",
        cascade="all, delete-orphan",
    )
    creator: Mapped["Member | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member", foreign_keys=[created_by]
    )

    def __repr__(self) -> str:
        return f"<ClubEvent id={self.id} title={self.title!r}>"


class EventRegistration(db.Model):
    """Registration model with status tracking for events."""

    __tablename__ = "event_registrations"
    __table_args__ = (
        UniqueConstraint("event_id", "member_id", name="uq_event_registration"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("club_events.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    # registered | approved | waitlisted | cancelled | attended
    status: Mapped[str] = mapped_column(
        db.String(50), default="registered", nullable=False
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    guests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    event: Mapped["ClubEvent"] = relationship(
        "ClubEvent", back_populates="registrations", foreign_keys=[event_id]
    )
    member: Mapped["Member"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member", foreign_keys=[member_id]
    )

    def __repr__(self) -> str:
        return f"<EventRegistration event_id={self.event_id} member_id={self.member_id} status={self.status!r}>"
