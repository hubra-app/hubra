"""Marshmallow schemas for ClubEvent and EventRegistration."""

from marshmallow import EXCLUDE, RAISE, fields, validate

from hubra.core.extensions import ma
from hubra.core.models.event import ClubEvent, EventRegistration
from hubra.core.schemas.counts import cached_count, clear_counts, prime_counts

_EVENT_TYPES = ["Workshop", "Social", "Certification", "Meeting"]


def club_event_types() -> list[str]:
    """The types this club picks from: its own list, or the built-in four."""
    from hubra.core.modules.state import get_config

    raw = str(get_config("events").get("event_types") or "")
    own = [t.strip()[:50] for t in raw.split(",") if t.strip()]
    return own or list(_EVENT_TYPES)


def _valid_type(value: str) -> None:
    # The built-in types stay valid, so older events still save after a club
    # switched to its own list.
    if value not in _EVENT_TYPES and value not in club_event_types():
        from marshmallow import ValidationError

        raise ValidationError("Unknown event type")
_EVENT_CATEGORIES = ["general", "training", "social", "meeting", "competition"]
# Registrations that hold a place.
_ACTIVE_REGISTRATION = ["registered", "approved", "attended"]
_REGISTRATION_COUNT = "_registration_count"
_PENDING_COUNT = "_pending_count"
_PLACES_TAKEN = "_places_taken"


class ClubEventSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = ClubEvent
        load_instance = True
        unknown = EXCLUDE
        exclude = ("attendees", "registrations", "creator")

    date = fields.Date()
    end_date = fields.Date(allow_none=True, dump_default=None)
    all_day = fields.Bool(dump_default=False)
    max_attendees = fields.Int(allow_none=True, dump_default=None)
    requires_approval = fields.Bool(dump_default=False)
    is_public = fields.Bool(dump_default=False)
    category = fields.Str(dump_default="general")
    color = fields.Str(allow_none=True, dump_default=None)
    cover_image_url = fields.Str(allow_none=True, dump_default=None)
    meeting_url = fields.Str(allow_none=True, dump_default=None)
    description = fields.Str(allow_none=True, dump_default=None)
    created_by = fields.Int(allow_none=True, dump_default=None)
    registration_deadline = fields.DateTime(allow_none=True, dump_default=None)
    cancellation_deadline = fields.DateTime(allow_none=True, dump_default=None)

    # List of member IDs from the M:N relationship (backward compat)
    attendee_ids = fields.Method("get_attendee_ids", dump_only=True)

    # Registration count
    registration_count = fields.Method("get_registration_count", dump_only=True)
    # Places taken against max_attendees: each registration with its guests.
    places_taken = fields.Method("get_places_taken", dump_only=True)
    # Sign-ups waiting for an organiser (events that need approval).
    pending_count = fields.Method("get_pending_count", dump_only=True)
    # The viewer's own registration: registered, approved, pending,
    # waitlisted, attended, declined, or None.
    my_status = fields.Method("get_my_status", dump_only=True)

    def dump(self, obj, *, many=None):
        if not (self.many if many is None else many):
            return super().dump(obj, many=many)
        events = list(obj)
        prime_counts(
            events,
            _REGISTRATION_COUNT,
            EventRegistration.event_id,
            EventRegistration.status.in_(_ACTIVE_REGISTRATION),
        )
        prime_counts(
            events,
            _PENDING_COUNT,
            EventRegistration.event_id,
            EventRegistration.status == "pending",
        )
        _prime_places(events)
        try:
            return super().dump(events, many=many)
        finally:
            clear_counts(events, _REGISTRATION_COUNT, _PENDING_COUNT, _PLACES_TAKEN)

    def get_attendee_ids(self, obj):
        return [m.id for m in (obj.attendees or [])]

    def get_registration_count(self, obj):
        from sqlalchemy import func, select

        return cached_count(
            obj,
            _REGISTRATION_COUNT,
            lambda: db.session.scalar(
                select(func.count())
                .select_from(EventRegistration)
                .where(
                    EventRegistration.event_id == obj.id,
                    EventRegistration.status.in_(_ACTIVE_REGISTRATION),
                )
            ),
        )


    def get_places_taken(self, obj):
        from hubra.api.events.services import EventService

        return cached_count(
            obj, _PLACES_TAKEN, lambda: EventService.places_taken(obj.id)
        )

    def get_pending_count(self, obj):
        from sqlalchemy import func, select

        return cached_count(
            obj,
            _PENDING_COUNT,
            lambda: db.session.scalar(
                select(func.count())
                .select_from(EventRegistration)
                .where(
                    EventRegistration.event_id == obj.id,
                    EventRegistration.status == "pending",
                )
            ),
        )

    def get_my_status(self, obj):
        return _my_statuses().get(obj.id)


def _prime_places(events) -> None:
    """One grouped query for every event's places taken."""
    from sqlalchemy import func, select

    from hubra.api.events.services import _HOLDS_A_PLACE

    ids = [e.id for e in events]
    places: dict[int, int] = {}
    if ids:
        places = dict(
            db.session.execute(
                select(
                    EventRegistration.event_id,
                    func.sum(1 + EventRegistration.guests),
                )
                .where(
                    EventRegistration.event_id.in_(ids),
                    EventRegistration.status.in_(_HOLDS_A_PLACE),
                )
                .group_by(EventRegistration.event_id)
            ).all()
        )
    for e in events:
        e.__dict__[_PLACES_TAKEN] = int(places.get(e.id, 0))


def _my_statuses() -> dict[int, str]:
    """The current member's registration status per event, loaded once per
    request ({} outside a member's request)."""
    from flask import has_request_context, request
    from sqlalchemy import select

    if not has_request_context():
        return {}
    # Kept on the request itself: g can outlive one request (tests).
    cached = request.environ.get("hubra.my_event_statuses")
    if cached is not None:
        return cached
    from hubra.api.permissions import _current_member

    try:
        member = _current_member()
    except Exception:
        member = None
    statuses: dict[int, str] = {}
    if member is not None and getattr(member, "roles", None) is not None:
        statuses = dict(
            db.session.execute(
                select(EventRegistration.event_id, EventRegistration.status).where(
                    EventRegistration.member_id == member.id,
                    EventRegistration.status != "cancelled",
                )
            ).all()
        )
    request.environ["hubra.my_event_statuses"] = statuses
    return statuses


from hubra.core.extensions import db  # noqa: E402 — needed by get_registration_count


class ClubEventCreateSchema(ma.Schema):
    class Meta:
        unknown = RAISE

    title = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    date = fields.Date(required=True)
    time = fields.Str(allow_none=True, load_default=None)
    location = fields.Str(allow_none=True, load_default=None)
    type = fields.Str(required=True, validate=_valid_type)
    description = fields.Str(allow_none=True, load_default=None)
    meeting_url = fields.Str(allow_none=True, load_default=None)
    end_date = fields.Date(allow_none=True, load_default=None)
    all_day = fields.Bool(load_default=False)
    category = fields.Str(
        load_default="general", validate=validate.OneOf(_EVENT_CATEGORIES)
    )
    max_attendees = fields.Int(
        allow_none=True, load_default=None, validate=validate.Range(min=0)
    )
    registration_deadline = fields.DateTime(allow_none=True, load_default=None)
    cancellation_deadline = fields.DateTime(allow_none=True, load_default=None)
    requires_approval = fields.Bool(load_default=False)
    is_public = fields.Bool(load_default=False)
    cover_image_url = fields.Str(allow_none=True, load_default=None)
    color = fields.Str(
        allow_none=True,
        load_default=None,
        validate=validate.Regexp(r"^#[0-9A-Fa-f]{6}$"),
    )


class ClubEventUpdateSchema(ma.Schema):
    """PATCH — all fields optional."""

    class Meta:
        unknown = RAISE

    title = fields.Str(validate=validate.Length(min=1, max=255))
    date = fields.Date()
    time = fields.Str(allow_none=True)
    location = fields.Str(allow_none=True)
    type = fields.Str(validate=_valid_type)
    description = fields.Str(allow_none=True)
    meeting_url = fields.Str(allow_none=True)
    end_date = fields.Date(allow_none=True)
    all_day = fields.Bool()
    category = fields.Str(validate=validate.OneOf(_EVENT_CATEGORIES))
    max_attendees = fields.Int(allow_none=True, validate=validate.Range(min=0))
    registration_deadline = fields.DateTime(allow_none=True)
    cancellation_deadline = fields.DateTime(allow_none=True)
    requires_approval = fields.Bool()
    is_public = fields.Bool()
    cover_image_url = fields.Str(allow_none=True)
    color = fields.Str(allow_none=True, validate=validate.Regexp(r"^#[0-9A-Fa-f]{6}$"))


class EventRegistrationSchema(ma.Schema):
    """Schema for event registration records."""

    class Meta:
        unknown = EXCLUDE

    id = fields.Int(dump_only=True)
    event_id = fields.Int(dump_only=True)
    member_id = fields.Int(dump_only=True)
    member_name = fields.Method("get_member_name", dump_only=True)
    status = fields.Str(dump_default="registered")
    registered_at = fields.DateTime(dump_only=True)
    cancelled_at = fields.DateTime(allow_none=True, dump_only=True, dump_default=None)
    attended_at = fields.DateTime(allow_none=True, dump_only=True, dump_default=None)
    notes = fields.Str(allow_none=True, dump_default=None)
    guests = fields.Int(dump_default=0)

    def get_member_name(self, obj):
        return obj.member.name if obj.member else None


class RegisterSchema(ma.Schema):
    """Schema for registering for an event."""

    class Meta:
        unknown = RAISE

    notes = fields.Str(allow_none=True, load_default=None)
    guests = fields.Int(load_default=0, validate=validate.Range(min=0))
