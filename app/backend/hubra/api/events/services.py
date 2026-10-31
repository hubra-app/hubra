"""Event service — business logic for club events, attendees, and registrations."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import selectinload

from hubra.api.notifications.services import notify_on_publish
from hubra.api.utils import log_audit
from hubra.core.errors import ApiError, raise_error
from hubra.core.extensions import db
from hubra.core.models.event import ClubEvent, EventRegistration, event_attendees
from hubra.core.models.member import Member
from hubra.core.modules import emit
from hubra.core.modules.events import EVENT_PUBLISHED


# Registration states that take one of the event's places (the member's
# and their guests'). "pending" waits for an organiser on an event that needs
# approval and takes none yet; "declined" is the organiser's no.
_HOLDS_A_PLACE = ("registered", "approved", "attended")
# A registration a member still has, so they cannot sign up again.
_OPEN = ("registered", "approved", "waitlisted", "pending")


def _passed(deadline: datetime | None) -> bool:
    """Whether a deadline is set and over (SQLite hands back naive UTC)."""
    if deadline is None:
        return False
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    return deadline < datetime.now(timezone.utc)



def _check_dates(start, end) -> None:
    """An event cannot end before it starts (calendar apps drop it)."""
    if start is not None and end is not None and end < start:
        raise_error(400, "VALIDATION_ERROR", "end_date is before date")


def _tell_registered(event, title: str, skip_member_id: int | None = None) -> None:
    """Notify those signed up for (or waiting on) an upcoming event."""
    from hubra.api.notifications.services import notify_member

    if (event.end_date or event.date) < date.today():
        return
    for reg in event.registrations:
        if reg.status in _OPEN and reg.member_id != skip_member_id:
            notify_member(
                reg.member_id, "info", title, event.title, link=event_link(event.id)
            )

def event_link(event_id: int, pending: bool = False) -> str:
    """The events page showing one event (``pending`` opens its sign-ups
    waiting for approval)."""
    link = f"/app/operations/events?event={event_id}"
    return link + "&pending=1" if pending else link


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
    def update(
        event: ClubEvent,
        data: dict,
        actor_id: int,
        quiet: bool = False,
        audit: bool = True,
    ) -> ClubEvent:
        """Update allowed fields on an event.

        ``quiet`` leaves telling those signed up to the caller (a series
        change tells each member once); ``audit=False`` leaves the audit
        entry to it.
        """
        before = (event.date, event.time, event.end_date, event.location)
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
            "group_id",
        ):
            if field in data:
                setattr(event, field, data[field])
        if "date" in data or "end_date" in data:
            _check_dates(event.date, event.end_date)
        if not quiet and (event.date, event.time, event.end_date, event.location) != before:
            _tell_registered(event, "Event changed", skip_member_id=actor_id)
        if data.get("requires_approval") is False:
            # Approval switched off: whoever is waiting for it is let in, in
            # the order they asked (or put on the waitlist if it is full).
            EventService._lock(event.id)
            for reg in db.session.scalars(
                select(EventRegistration)
                .where(
                    EventRegistration.event_id == event.id,
                    EventRegistration.status == "pending",
                )
                .order_by(EventRegistration.registered_at, EventRegistration.id)
            ).all():
                EventService._admit(event, reg)
        if "max_attendees" in data:
            # More places (or no limit any more): the waitlist moves up.
            EventService._lock(event.id)
            db.session.flush()
            EventService._promote_waitlist(event)

        if not audit:
            return event
        log_audit(
            actor_id=actor_id,
            action="update_event",
            target_type="Event",
            target_id=event.id,
            target_label=event.title,
        )
        return event

    @staticmethod
    def delete(event_id: int, actor_id: int, scope: str = "this") -> None:
        """Delete an event; ``scope="following"`` also the later dates of
        its series."""
        from hubra.api.events import series

        event = EventService.get(event_id)
        if scope == "following":
            series.delete_following(event, actor_id)
            return
        series.delete_one(event)

        log_audit(
            actor_id=actor_id,
            action="delete_event",
            target_type="Event",
            target_id=event.id,
            target_label=event.title,
        )
        # Those who signed up hear that it is off rather than turn up.
        _tell_registered(event, "Event cancelled", skip_member_id=actor_id)
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
        own: bool = False,
    ) -> EventRegistration:
        """Register a member for an event. Handles waitlist when full.

        A member has one registration row per event: signing up again after
        cancelling brings the cancelled row back. Waitlisted members are not
        attendees until they get a place. A member signing up themselves
        (``own``) cannot after the registration deadline or the event;
        an organiser still can.
        """
        event = EventService.get(event_id)
        EventService._lock(event_id)
        if own:
            last_day = event.end_date or event.date
            if _passed(event.registration_deadline) or last_day < date.today():
                raise_error(
                    409, "REGISTRATION_CLOSED", "Registration for this event is closed"
                )

        member = db.session.get(Member, member_id)
        if member is None or member.archived_at is not None:
            raise_error(404, "NOT_FOUND", f"Member {member_id} not found")

        registration = db.session.scalar(
            select(EventRegistration).where(
                EventRegistration.event_id == event_id,
                EventRegistration.member_id == member_id,
            )
        )
        if registration is not None and registration.status in _OPEN:
            raise_error(409, "CONFLICT", "Already registered for this event")

        # A member asking for a place on an event that needs approval waits
        # for an organiser; an organiser signing someone up approves it.
        if own and event.requires_approval:
            status = "pending"
        elif EventService._is_full(
            event, needed=1 + guests
        ) or EventService._has_waitlist(event.id):
            # Nobody gets ahead of those already waiting (a free place may
            # only be too small for the first in line and their guests).
            status = "waitlisted"
        else:
            status = "approved" if event.requires_approval else "registered"

        if registration is None:
            registration = EventRegistration(event_id=event_id, member_id=member_id)
            db.session.add(registration)
        registration.status = status
        registration.notes = notes
        registration.guests = guests
        registration.registered_at = datetime.now(timezone.utc)
        registration.cancelled_at = None

        if status in _HOLDS_A_PLACE:
            EventService._ensure_attendee(event_id, member)
        if status == "pending":
            from hubra.api.notifications.staff import notify_permitted

            notify_permitted(
                "events.events.add_attendee",
                "info",
                "Sign-up to approve",
                f"{member.name}: {event.title}",
                skip_member_id=member.id,
                link=event_link(event_id, pending=True),
            )

        return registration

    @staticmethod
    def _admit(event: ClubEvent, registration: EventRegistration) -> None:
        """Give an approved registration its place, or the waitlist when the
        event is full (with the member's guests)."""
        if EventService._is_full(
            event, needed=1 + (registration.guests or 0)
        ) or EventService._has_waitlist(event.id):
            registration.status = "waitlisted"
        else:
            registration.status = "approved"
            member = db.session.get(Member, registration.member_id)
            if member is not None:
                EventService._ensure_attendee(event.id, member)
        db.session.flush()

    @staticmethod
    def decide(event_id: int, member_id: int, approve: bool, actor_id: int):
        """An organiser approves or declines a pending sign-up."""
        from hubra.api.notifications.services import notify_member

        event = EventService.get(event_id)
        EventService._lock(event_id)
        registration = db.session.scalar(
            select(EventRegistration).where(
                EventRegistration.event_id == event_id,
                EventRegistration.member_id == member_id,
            )
        )
        if registration is None or registration.status != "pending":
            raise_error(409, "NOT_PENDING", "This sign-up is not waiting for approval")
        if approve:
            EventService._admit(event, registration)
            title = (
                "Sign-up confirmed"
                if registration.status == "approved"
                else "Sign-up confirmed, on the waitlist"
            )
        else:
            registration.status = "declined"
            title = "Sign-up declined"
        notify_member(member_id, "info", title, event.title, link=event_link(event.id))
        log_audit(
            actor_id=actor_id,
            action="approve_registration" if approve else "decline_registration",
            target_type="Event",
            target_id=event.id,
            target_label=event.title,
        )
        return registration

    @staticmethod
    def registrations(event_id: int, status: str | None = None):
        """An event's registrations, oldest first (for the organisers)."""
        EventService.get(event_id)
        query = (
            select(EventRegistration)
            .where(EventRegistration.event_id == event_id)
            .options(selectinload(EventRegistration.member).selectinload(Member.user))
            .order_by(EventRegistration.registered_at, EventRegistration.id)
        )
        if status:
            query = query.where(EventRegistration.status == status)
        return db.session.scalars(query).all()

    @staticmethod
    def _lock(event_id: int) -> None:
        """Serialize sign-ups and cancellations of one event until commit, so
        two people cannot both take its last place (Postgres; SQLite has
        no row locks and runs one writer anyway)."""
        db.session.execute(
            select(ClubEvent.id).where(ClubEvent.id == event_id).with_for_update()
        )

    @staticmethod
    def places_taken(event_id: int) -> int:
        """Places taken: each registration that holds one, with its guests."""
        return (
            db.session.scalar(
                select(func.sum(1 + EventRegistration.guests)).where(
                    EventRegistration.event_id == event_id,
                    EventRegistration.status.in_(_HOLDS_A_PLACE),
                )
            )
            or 0
        )

    @staticmethod
    def _has_waitlist(event_id: int) -> bool:
        return (
            db.session.scalar(
                select(EventRegistration.id)
                .where(
                    EventRegistration.event_id == event_id,
                    EventRegistration.status == "waitlisted",
                )
                .limit(1)
            )
            is not None
        )

    @staticmethod
    def _is_full(event: ClubEvent, needed: int = 1) -> bool:
        """Whether *needed* more places (a member and their guests) no longer
        fit within the event's limit."""
        if not event.max_attendees or event.max_attendees <= 0:
            return False
        return EventService.places_taken(event.id) + needed > event.max_attendees

    @staticmethod
    def _ensure_attendee(event_id: int, member: Member) -> None:
        """Attendees table, kept for older screens and the calendar."""
        try:
            EventService.add_attendee(event_id, member)
        except ApiError:
            pass  # already in the attendees table

    @staticmethod
    def cancel_registration(
        event_id: int, member_id: int, own: bool = False
    ) -> EventRegistration | None:
        """Cancel a member's registration; the first on the waitlist moves up.

        After the cancellation deadline a member can no longer cancel their
        own place (``own``); a waitlist entry can always be withdrawn.
        """
        EventService._lock(event_id)
        registration = db.session.scalar(
            select(EventRegistration).where(
                EventRegistration.event_id == event_id,
                EventRegistration.member_id == member_id,
                EventRegistration.status.in_(_OPEN),
            )
        )
        if registration is None:
            # Put on the list by an organiser, without a registration.
            try:
                EventService.remove_attendee(event_id, member_id)
            except ApiError:
                raise_error(404, "NOT_FOUND", "No active registration found")
            return None
        if (
            own
            and registration.status in _HOLDS_A_PLACE
            and _passed(EventService.get(event_id).cancellation_deadline)
        ):
            raise_error(
                409,
                "CANCELLATION_CLOSED",
                "The cancellation deadline for this event has passed",
            )

        freed_a_place = registration.status in _HOLDS_A_PLACE
        registration.status = "cancelled"
        registration.cancelled_at = datetime.now(timezone.utc)

        # Remove from attendees for backward compat
        try:
            EventService.remove_attendee(event_id, member_id)
        except ApiError:
            pass

        if freed_a_place:
            db.session.flush()
            EventService._promote_waitlist(EventService.get(event_id))

        return registration

    @staticmethod
    def _promote_waitlist(event: ClubEvent) -> None:
        """Give free places to the waitlist, first come first served: the
        first in line moves up once there is room for them and their guests."""
        while True:
            nxt = db.session.scalar(
                select(EventRegistration)
                .where(
                    EventRegistration.event_id == event.id,
                    EventRegistration.status == "waitlisted",
                )
                .order_by(EventRegistration.registered_at, EventRegistration.id)
                .limit(1)
            )
            if nxt is None or EventService._is_full(event, needed=1 + nxt.guests):
                return
            nxt.status = "approved" if event.requires_approval else "registered"
            db.session.flush()
            member = db.session.get(Member, nxt.member_id)
            if member is not None:
                EventService._ensure_attendee(event.id, member)
            # They may have given up on it; tell them they are in now.
            from hubra.api.notifications.services import notify_member

            notify_member(
                nxt.member_id,
                "info",
                "You got a place",
                event.title,
                link=event_link(event.id),
            )

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
    def generate_ical(events: list[ClubEvent], name: str | None = None) -> str:
        """Generate an iCalendar (RFC 5545) feed for a list of events.

        Events with a ``time`` like "14:00-18:00" get local start and end
        times (Europe/Zurich); others are all-day.
        """
        from hubra.core.tenant.context import current_tenant

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        # Event ids repeat across clubs (one schema each): the club's slug
        # keeps the UIDs apart for someone who subscribes to two clubs.
        tenant = current_tenant()
        uid_host = f"{tenant.slug}.hubra" if tenant else "hubra"
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Hubra//Event Calendar//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
        ]
        if name:
            lines.append(f"X-WR-CALNAME:{_ical_text(name)}")
        lines.append("X-WR-TIMEZONE:Europe/Zurich")
        lines += _ZURICH_VTIMEZONE

        for event in events:
            lines += [
                "BEGIN:VEVENT",
                f"UID:event-{event.id}@{uid_host}",
                f"DTSTAMP:{stamp}",
                f"SUMMARY:{_ical_text(event.title)}",
            ]
            start, end = _event_times(event)
            if start is None:
                last = event.end_date or event.date
                lines.append(f"DTSTART;VALUE=DATE:{event.date:%Y%m%d}")
                # DTEND of an all-day event is exclusive.
                lines.append(f"DTEND;VALUE=DATE:{last + timedelta(days=1):%Y%m%d}")
            else:
                lines.append(f"DTSTART;TZID=Europe/Zurich:{start:%Y%m%dT%H%M%S}")
                lines.append(f"DTEND;TZID=Europe/Zurich:{end:%Y%m%dT%H%M%S}")
            if event.location:
                lines.append(f"LOCATION:{_ical_text(event.location)}")
            description = event.description or ""
            if event.meeting_url:
                description = f"{description}\n\n{event.meeting_url}".strip()
                # The URL property is not escaped text; a line break in it
                # would start a new calendar property.
                if re.fullmatch(r"https?://\S+", event.meeting_url):
                    lines.append(f"URL:{event.meeting_url}")
            if description:
                lines.append(f"DESCRIPTION:{_ical_text(description)}")
            lines += [f"CATEGORIES:{_ical_text(event.type)}", "END:VEVENT"]

        lines.append("END:VCALENDAR")
        return "\r\n".join(_fold(line) for line in lines) + "\r\n"


_ZURICH_VTIMEZONE = [
    "BEGIN:VTIMEZONE",
    "TZID:Europe/Zurich",
    "BEGIN:DAYLIGHT",
    "TZOFFSETFROM:+0100",
    "TZOFFSETTO:+0200",
    "TZNAME:CEST",
    "DTSTART:19700329T020000",
    "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
    "END:DAYLIGHT",
    "BEGIN:STANDARD",
    "TZOFFSETFROM:+0200",
    "TZOFFSETTO:+0100",
    "TZNAME:CET",
    "DTSTART:19701025T030000",
    "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
    "END:STANDARD",
    "END:VTIMEZONE",
]


def _ical_text(value: str) -> str:
    """Escape a TEXT value (RFC 5545 3.3.11)."""
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def _fold(line: str) -> str:
    """Fold lines longer than 75 octets (RFC 5545 3.1)."""
    data = line.encode("utf-8")
    if len(data) <= 75:
        return line
    parts, chunk = [], b""
    for ch in line:
        enc = ch.encode("utf-8")
        if len(chunk) + len(enc) > (75 if not parts else 74):
            parts.append(chunk.decode("utf-8"))
            chunk = b""
        chunk += enc
    parts.append(chunk.decode("utf-8"))
    return "\r\n ".join(parts)


_TIME_RANGE = re.compile(r"^\s*(\d{1,2})[:.](\d{2})\s*(?:-\s*(\d{1,2})[:.](\d{2}))?")


def _event_times(event: ClubEvent):
    """Local start and end datetimes, or (None, None) for all-day events."""
    if event.all_day or not event.time:
        return None, None
    m = _TIME_RANGE.match(event.time)
    if not m:
        return None, None
    try:
        start = datetime.combine(event.date, time(int(m[1]), int(m[2])))
        if m[3]:
            end = datetime.combine(
                event.end_date or event.date, time(int(m[3]), int(m[4]))
            )
        else:
            end = start + timedelta(hours=1)
    except ValueError:
        return None, None
    if end <= start:
        end = start + timedelta(hours=1)
    return start, end


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
            .options(selectinload(ClubEvent.attendees))
            .order_by(ClubEvent.date)
        )

        if from_str:
            try:
                from_date = date.fromisoformat(from_str)
                # An event that started earlier and is still on counts too.
                query = query.where(
                    func.coalesce(ClubEvent.end_date, ClubEvent.date) >= from_date
                )
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
        _check_dates(data.get("date"), data.get("end_date"))
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
            group_id=data.get("group_id"),
            created_by=actor_id,
        )
        db.session.add(event)
        db.session.flush()
        if data.get("recurrence"):
            from hubra.api.events.series import create_series

            create_series(event, data["recurrence"], actor_id)

        notify_on_publish(
            "events",
            "info",
            "New event",
            event.title,
            skip_member_id=actor_id,
            link=event_link(event.id),
        )
        emit(EVENT_PUBLISHED, event_id=event.id)

        log_audit(
            actor_id=actor_id,
            action="create_event",
            target_type="Event",
            target_id=event.id,
            target_label=event.title,
        )

        db.session.refresh(event)
        return EventService.get(event.id)
