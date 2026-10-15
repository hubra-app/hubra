"""Event service — business logic for club events, attendees, and registrations."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import selectinload

from vollbuild.api.notifications.services import notify_all_active
from vollbuild.api.utils import log_audit
from vollbuild.core.errors import raise_error
from vollbuild.core.extensions import db
from vollbuild.core.models.event import ClubEvent, EventRegistration, event_attendees
from vollbuild.core.models.member import Member


class EventService:
    """Operations on a single event."""

    @staticmethod
    def get(event_id: int) -> ClubEvent:
        """Return an event with attendees eager-loaded, or raise 404."""
        event = db.session.scalar(
            select(ClubEvent)
            .where(ClubEvent.id == event_id)
            .options(
                selectinload(ClubEvent.attendees),
                selectinload(ClubEvent.registrations),
            )
        )
        if event is None:
            raise_error(404, "NOT_FOUND", f"Event {event_id} not found")
        return event  # type: ignore[return-value]

    @staticmethod
    def update(event: ClubEvent, data: dict, actor_id: int) -> ClubEvent:
        """Update allowed fields on an event."""
        for field in (
            "title",
            "date",
            "time",
            "location",
            "type",
            "description",
            "meeting_url",
            "end_date",
            "all_day",
            "category",
            "max_attendees",
            "registration_deadline",
            "cancellation_deadline",
            "requires_approval",
            "is_public",
            "cover_image_url",
            "color",
        ):
            if field in data:
                setattr(event, field, data[field])

        log_audit(
            actor_id=actor_id,
            action="update_event",
            target_type="Event",
            target_id=event.id,
            target_label=event.title,
        )
        return event

    @staticmethod
    def delete(event_id: int, actor_id: int) -> None:
        """Delete an event."""
        event = EventService.get(event_id)

        log_audit(
            actor_id=actor_id,
            action="delete_event",
            target_type="Event",
            target_id=event.id,
            target_label=event.title,
        )
        db.session.delete(event)

    @staticmethod
    def add_attendee(event_id: int, member: Member) -> None:
        """Add a member as an event attendee. Raises 409 if already attending."""
        already = db.session.scalar(
            select(func.count())
            .select_from(event_attendees)
            .where(
                event_attendees.c.event_id == event_id,
                event_attendees.c.member_id == member.id,
            )
        )
        if already:
            raise_error(
                409,
                "CONFLICT",
                f"Member {member.id} is already attending event {event_id}",
            )

        db.session.execute(
            insert(event_attendees).values(event_id=event_id, member_id=member.id)
        )

    @staticmethod
    def remove_attendee(event_id: int, member_id: int) -> None:
        """Remove a member from event attendees. Raises 404 if not attending."""
        attending = db.session.scalar(
            select(func.count())
            .select_from(event_attendees)
            .where(
                event_attendees.c.event_id == event_id,
                event_attendees.c.member_id == member_id,
            )
        )
        if not attending:
            raise_error(
                404,
                "NOT_FOUND",
                f"Member {member_id} is not attending event {event_id}",
            )

        db.session.execute(
            delete(event_attendees).where(
                event_attendees.c.event_id == event_id,
                event_attendees.c.member_id == member_id,
            )
        )

    # ── Registration workflow ─────────────────────────────────────────────────

    @staticmethod
    def register(
        event_id: int,
        member_id: int,
        notes: str | None = None,
        guests: int = 0,
    ) -> EventRegistration:
        """Register a member for an event. Handles waitlist when full."""
        event = EventService.get(event_id)

        member = db.session.get(Member, member_id)
        if member is None or member.archived_at is not None:
            raise_error(404, "NOT_FOUND", f"Member {member_id} not found")

        # Check if already registered
        existing = db.session.scalar(
            select(EventRegistration).where(
                EventRegistration.event_id == event_id,
                EventRegistration.member_id == member_id,
                EventRegistration.status.in_(["registered", "approved", "waitlisted"]),
            )
        )
        if existing is not None:
            raise_error(409, "CONFLICT", "Already registered for this event")

        # Check max attendees
        status = "registered"
        if event.requires_approval:
            status = "registered"  # needs admin approval

        if event.max_attendees is not None and event.max_attendees > 0:
            active_count = (
                db.session.scalar(
                    select(func.count())
                    .select_from(EventRegistration)
                    .where(
                        EventRegistration.event_id == event_id,
                        EventRegistration.status.in_(
                            ["registered", "approved", "attended"]
                        ),
                    )
                )
                or 0
            )
            if active_count >= event.max_attendees:
                status = "waitlisted"

        registration = EventRegistration(
            event_id=event_id,
            member_id=member_id,
            status=status,
            notes=notes,
            guests=guests,
        )
        db.session.add(registration)

        # Also add to attendees for backward compat
        try:
            EventService.add_attendee(event_id, member)
        except Exception:
            pass  # Already in attendees table

        return registration

    @staticmethod
    def cancel_registration(event_id: int, member_id: int) -> EventRegistration:
        """Cancel a member's registration for an event."""
        registration = db.session.scalar(
            select(EventRegistration).where(
                EventRegistration.event_id == event_id,
                EventRegistration.member_id == member_id,
                EventRegistration.status.in_(["registered", "approved", "waitlisted"]),
            )
        )
        if registration is None:
            raise_error(404, "NOT_FOUND", "No active registration found")

        registration.status = "cancelled"
        registration.cancelled_at = datetime.now(timezone.utc)

        # Remove from attendees for backward compat
        try:
            EventService.remove_attendee(event_id, member_id)
        except Exception:
            pass

        return registration

    @staticmethod
    def mark_attendance(event_id: int, member_id: int) -> EventRegistration:
        """Mark a member as attended for an event."""
        registration = db.session.scalar(
            select(EventRegistration).where(
                EventRegistration.event_id == event_id,
                EventRegistration.member_id == member_id,
            )
        )
        if registration is None:
            raise_error(404, "NOT_FOUND", "No registration found for this member")

        registration.status = "attended"
        registration.attended_at = datetime.now(timezone.utc)

        return registration

    @staticmethod
    def generate_ical(events: list[ClubEvent]) -> str:
        """Generate iCal format calendar data for a list of events."""
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Club Management Suite//Event Calendar//EN",
            "CALSCALE:GREGORIAN",
        ]

        for event in events:
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:{event.id}@club-management-suite",
                    f"SUMMARY:{event.title}",
                    f"DTSTART:{event.date.isoformat().replace('-', '')}",
                ]
            )
            if event.end_date:
                lines.append(f"DTEND:{event.end_date.isoformat().replace('-', '')}")
            if event.location:
                lines.append(f"LOCATION:{event.location}")
            if event.description:
                lines.append(f"DESCRIPTION:{event.description}")
            if event.time:
                lines.append(f"COMMENT:Time: {event.time}")
            lines.extend(
                [
                    f"CATEGORIES:{event.type}",
                    "END:VEVENT",
                ]
            )

        lines.append("END:VCALENDAR")
        return "\r\n".join(lines)


class EventsService:
    """Operations on the event collection."""

    @staticmethod
    def list(
        from_str: str = "",
        to_str: str = "",
        type_filter: str = "",
        category: str = "",
    ) -> list[ClubEvent]:
        """Return events with optional date range, type, and category filtering."""
        query = (
            select(ClubEvent)
            .options(
                selectinload(ClubEvent.attendees),
                selectinload(ClubEvent.registrations),
            )
            .order_by(ClubEvent.date)
        )

        if from_str:
            try:
                from_date = date.fromisoformat(from_str)
                query = query.where(ClubEvent.date >= from_date)
            except ValueError:
                raise_error(
                    400,
                    "VALIDATION_ERROR",
                    "Invalid 'from' date format. Use ISO 8601 (YYYY-MM-DD).",
                )

        if to_str:
            try:
                to_date = date.fromisoformat(to_str)
                query = query.where(ClubEvent.date <= to_date)
            except ValueError:
                raise_error(
                    400,
                    "VALIDATION_ERROR",
                    "Invalid 'to' date format. Use ISO 8601 (YYYY-MM-DD).",
                )

        if type_filter:
            query = query.where(ClubEvent.type == type_filter)

        if category:
            query = query.where(ClubEvent.category == category)

        return db.session.scalars(query).all()  # type: ignore[return-value]

    @staticmethod
    def create(data: dict, actor_id: int) -> ClubEvent:
        """Create a new event."""
        event = ClubEvent(
            title=data["title"],
            date=data["date"],
            time=data.get("time"),
            location=data.get("location"),
            type=data["type"],
            description=data.get("description"),
            meeting_url=data.get("meeting_url"),
            end_date=data.get("end_date"),
            all_day=data.get("all_day", False),
            category=data.get("category", "general"),
            max_attendees=data.get("max_attendees"),
            registration_deadline=data.get("registration_deadline"),
            cancellation_deadline=data.get("cancellation_deadline"),
            requires_approval=data.get("requires_approval", False),
            is_public=data.get("is_public", False),
            cover_image_url=data.get("cover_image_url"),
            color=data.get("color"),
            created_by=actor_id,
        )
        db.session.add(event)
        db.session.flush()

        notify_all_active("info", "New event", event.title, skip_member_id=actor_id)

        log_audit(
            actor_id=actor_id,
            action="create_event",
            target_type="Event",
            target_id=event.id,
            target_label=event.title,
        )

        db.session.refresh(event)
        return EventService.get(event.id)
