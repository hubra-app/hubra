"""What Events offers other modules through contracts (docs/contracts.md).

- ``events.event.get`` (query): an event's times and how many places are
  taken.
- ``events.event.create`` (action): a new event, checked like one made in
  the app.
- ``events.registration.set`` (action): sign a member up, off, or as
  "maybe", with the waitlist and the deadlines of the app.
- ``events.attendance.set`` (action): record one member's attendance.

Hubra's service errors come back as ``Refused`` with the same code
(``REGISTRATION_CLOSED``, ``CONFLICT``, ...).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


def _actor_id(ctx, given: int | None) -> int | None:
    if given is not None:
        return given
    return ctx.actor.id if ctx.actor is not None else None


def _event(event_id: int):
    from hubra.core.contracts import Refused
    from hubra.core.extensions import db
    from hubra.core.models.event import ClubEvent

    event = db.session.get(ClubEvent, event_id)
    if event is None:
        raise Refused(f"Event {event_id} not found", code="NOT_FOUND", status=404)
    return event


class EventRef(BaseModel):
    event_id: int


class EventInfo(BaseModel):
    id: int
    title: str
    # Local start and end (club time, no zone); None for all-day events or
    # a time Hubra can't read.
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    places_taken: int
    maybe: int


def get_event(ctx, data: EventRef) -> EventInfo:
    from hubra.api.events.services import EventService, _event_times

    event = _event(data.event_id)
    start, end = _event_times(event)
    return EventInfo(
        id=event.id,
        title=event.title,
        starts_at=start,
        ends_at=end,
        places_taken=EventService.places_taken(event.id),
        maybe=EventService.maybe_count(event.id),
    )


class EventCreateIn(BaseModel):
    """The fields of the app's event form (``ClubEventCreateSchema``):
    title, date (ISO), time, all_day, location, description, is_public,
    type, ... They are checked like the form's."""

    model_config = ConfigDict(extra="allow")

    title: str
    date: str
    type: str
    actor_id: int | None = None


class EventCreated(BaseModel):
    id: int
    title: str
    date: str


def create_event(ctx, data: EventCreateIn) -> EventCreated:
    from marshmallow import ValidationError

    from hubra.api.events.services import EventsService
    from hubra.core.contracts import Refused
    from hubra.core.schemas.event import ClubEventCreateSchema

    body = data.model_dump(exclude={"actor_id"}, mode="json")
    try:
        fields = ClubEventCreateSchema().load(body)
    except ValidationError as exc:
        raise Refused(str(exc.messages), code="VALIDATION_ERROR", status=400) from None
    event = EventsService.create(fields, _actor_id(ctx, data.actor_id))
    return EventCreated(id=event.id, title=event.title, date=event.date.isoformat())


class RegistrationIn(BaseModel):
    event_id: int
    member_id: int
    status: Literal["registered", "cancelled", "maybe"]
    # The member answers for themselves: the deadlines apply, and an event
    # that needs approval waits for an organiser.
    own: bool = True
    notes: str | None = None
    guests: int = 0


class Registration(BaseModel):
    event_id: int
    member_id: int
    # What the member has now: registered, pending, waitlisted, maybe,
    # cancelled, ...
    status: str


def set_registration(ctx, data: RegistrationIn) -> Registration:
    from hubra.api.events.services import EventService

    if data.status == "registered":
        reg = EventService.register(
            event_id=data.event_id,
            member_id=data.member_id,
            notes=data.notes,
            guests=data.guests,
            own=data.own,
        )
    elif data.status == "maybe":
        reg = EventService.maybe(data.event_id, data.member_id, own=data.own)
    else:
        reg = EventService.cancel_registration(
            data.event_id, data.member_id, own=data.own
        )
    return Registration(
        event_id=data.event_id,
        member_id=data.member_id,
        status=reg.status if reg is not None else "cancelled",
    )


class AttendanceIn(BaseModel):
    event_id: int
    member_id: int
    # None takes the mark back.
    status: str | None = None
    actor_id: int | None = None


class Attendance(BaseModel):
    event_id: int
    member_id: int
    status: str | None = None


def set_attendance(ctx, data: AttendanceIn) -> Attendance:
    from hubra.api.events import attendance

    event = _event(data.event_id)
    attendance.set_status(
        event, data.member_id, data.status, actor_id=_actor_id(ctx, data.actor_id)
    )
    return Attendance(event_id=event.id, member_id=data.member_id, status=data.status)
