"""ClubEvent, EventSeries, EventRegistration and EventAttendance models, and
the event_attendees association table."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
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


# ── EventSeries ───────────────────────────────────────────────────────────────


class EventSeries(db.Model):
    """A weekly rule (a training every Tuesday until the summer holidays).

    Each date of the rule is an ordinary event (``ClubEvent.series_id``), so
    sign-ups and attendance work per date. The events carry the title, time
    and the rest; the series holds only the rule.
    """

    __tablename__ = "event_series"

    id: Mapped[int] = mapped_column(primary_key=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    until: Mapped[date] = mapped_column(Date, nullable=False)
    # Every n-th week, counted from the week of start_date.
    interval: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Weekdays as numbers, Monday 0 ... Sunday 6.
    weekdays: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    # Dates the rule leaves out (holidays, a date deleted on its own).
    skip_dates: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<EventSeries id={self.id} {self.start_date}..{self.until}>"


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
    # The group the event is for (a team's training): its members are
    # expected, which the attendance overview counts against.
    group_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("groups.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # A date of a recurring series, and the date of the rule it stands for
    # (it stays when this one date is moved).
    series_id: Mapped[int | None] = mapped_column(
        db.Integer,
        ForeignKey("event_series.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    series_date: Mapped[date | None] = mapped_column(Date, nullable=True)

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
    series: Mapped["EventSeries | None"] = relationship("EventSeries", lazy="selectin")

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


class EventAttendance(db.Model):
    """Who was there: taken by an organiser or trainer per event date.

    Kept apart from the sign-up, as most come to a training without signing
    up. ``present``, ``excused`` (told the trainer they could not come) or
    ``absent``; no row means not recorded.
    """

    __tablename__ = "event_attendance"
    __table_args__ = (
        UniqueConstraint("event_id", "member_id", name="uq_event_attendance"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        db.Integer,
        ForeignKey("club_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    member_id: Mapped[int] = mapped_column(
        db.Integer,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(db.String(20), nullable=False)
    marked_by: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    marked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<EventAttendance event_id={self.event_id} member_id={self.member_id} status={self.status!r}>"
