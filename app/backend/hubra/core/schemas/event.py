"""Marshmallow schemas for ClubEvent and EventRegistration."""

from marshmallow import EXCLUDE, RAISE, fields, validate

from hubra.core.extensions import ma
from hubra.core.models.event import ClubEvent, EventRegistration
from hubra.core.schemas.counts import cached_count, clear_counts, prime_counts

_EVENT_TYPES = ["Workshop", "Social", "Certification", "Meeting"]
_EVENT_CATEGORIES = ["general", "training", "social", "meeting", "competition"]
# Registrations that hold a place.
_ACTIVE_REGISTRATION = ["registered", "approved", "attended"]
_REGISTRATION_COUNT = "_registration_count"


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
        try:
            return super().dump(events, many=many)
        finally:
            clear_counts(events, _REGISTRATION_COUNT)

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


from hubra.core.extensions import db  # noqa: E402 — needed by get_registration_count


class ClubEventCreateSchema(ma.Schema):
    class Meta:
        unknown = RAISE

    title = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    date = fields.Date(required=True)
    time = fields.Str(allow_none=True, load_default=None)
    location = fields.Str(allow_none=True, load_default=None)
    type = fields.Str(required=True, validate=validate.OneOf(_EVENT_TYPES))
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
    type = fields.Str(validate=validate.OneOf(_EVENT_TYPES))
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
