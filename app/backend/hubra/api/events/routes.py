"""Events blueprint — CRUD and attendee management."""

from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, Response, current_app, g, jsonify, request, url_for
from itsdangerous import BadSignature, URLSafeSerializer
from hubra.api.auth.helpers import get_current_member
from marshmallow import ValidationError
from hubra.api.permissions import created_by, permission_required, require_member
from hubra.core.errors import api_error, raise_error
from hubra.core.extensions import db
from hubra.core.models.event import ClubEvent
from hubra.core.models.member import Member
from hubra.core.schemas.event import (
    AttendanceRollSchema,
    ClubEventCreateSchema,
    ClubEventSchema,
    ClubEventUpdateSchema,
    EventRegistrationSchema,
    RegisterSchema,
)
from hubra.api.events import attendance, series
from hubra.api.events.services import EventService, EventsService

events_bp = Blueprint("events_bp", __name__)

_event_schema = ClubEventSchema()
_events_schema = ClubEventSchema(many=True)
_create_schema = ClubEventCreateSchema()
_update_schema = ClubEventUpdateSchema()

# Whoever put an event up runs it: edits, cancels, and handles its sign-ups.
_own_event = created_by(ClubEvent, arg="event_id")


# ── GET /events ───────────────────────────────────────────────────────────────


@events_bp.get("/")
@permission_required("events", "read", "View events")
def list_events():
    args = request.args
    try:
        events = EventsService.list(
            from_str=args.get("from", "").strip(),
            to_str=args.get("to", "").strip(),
            type_filter=args.get("type", "").strip(),
            category=args.get("category", "").strip(),
        )
    except ValueError:
        return api_error(
            "VALIDATION_ERROR",
            "Invalid 'from' or 'to' date format. Use ISO 8601 (YYYY-MM-DD).",
            400,
        )
    return jsonify(_events_schema.dump(events)), 200


# ── GET /events/<id> ──────────────────────────────────────────────────────────


@events_bp.get("/<int:event_id>")
@permission_required("events", "read", "View events")
def get_event(event_id: int):
    event = EventService.get(event_id)
    return jsonify(_event_schema.dump(event)), 200


# ── POST /events ──────────────────────────────────────────────────────────────


@events_bp.post("/")
@permission_required("events", "create", "Create events")
def create_event():
    body = request.get_json(silent=True) or {}
    try:
        data = _create_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    event = EventsService.create(data, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(_event_schema.dump(event)), 201


# ── PATCH /events/<id> ────────────────────────────────────────────────────────


@events_bp.patch("/<int:event_id>")
@permission_required("events", "update", "Update events", allow=_own_event)
def update_event(event_id: int):
    event = EventService.get(event_id)

    body = request.get_json(silent=True) or {}
    try:
        data = _update_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    # A date of a series: ``?scope=following`` changes it and all later
    # dates (and may give them a new rule); otherwise just this one.
    if request.args.get("scope") == "following":
        rule = data.pop("recurrence", None)
        event = series.update_following(event, data, rule, get_current_member().id)
    elif "recurrence" in data:
        return api_error(
            "VALIDATION_ERROR", "recurrence changes need scope=following", 400
        )
    else:
        EventService.update(event, data, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    db.session.refresh(event)
    return jsonify(_event_schema.dump(event)), 200


# ── DELETE /events/<id> ───────────────────────────────────────────────────────


@events_bp.delete("/<int:event_id>")
@permission_required("events", "delete", "Delete events", allow=_own_event)
def delete_event(event_id: int):
    scope = "following" if request.args.get("scope") == "following" else "this"
    EventService.delete(event_id, get_current_member().id, scope)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── POST /events/<id>/attendees/<member_id> ───────────────────────────────────


@events_bp.post("/<int:event_id>/attendees/<int:member_id>")
@permission_required("events", "add_attendee", "Add event attendee", allow=_own_event)
def add_attendee(event_id: int, member_id: int):
    EventService.get(event_id)  # 404 if not found

    member = db.session.get(Member, member_id)
    if member is None or member.archived_at is not None:
        raise_error(404, "NOT_FOUND", f"Member {member_id} not found")
        return

    EventService.add_attendee(event_id, member)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── DELETE /events/<id>/attendees/<member_id> ─────────────────────────────────


@events_bp.delete("/<int:event_id>/attendees/<int:member_id>")
@permission_required("events", "remove_attendee", "Remove event attendee", allow=_own_event)
def remove_attendee(event_id: int, member_id: int):
    # Also ends their registration, so the place goes to the waitlist.
    EventService.cancel_registration(event_id, member_id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── POST /events/<id>/register — register current user ───────────────────────


@events_bp.post("/<int:event_id>/register")
@permission_required("events", "register", "Register for events")
def register_for_event(event_id: int):
    body = request.get_json(silent=True) or {}
    try:
        data = RegisterSchema().load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    member_id = get_current_member().id
    registration = EventService.register(
        event_id=event_id,
        member_id=member_id,
        notes=data.get("notes"),
        guests=data.get("guests", 0),
        own=True,
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(EventRegistrationSchema().dump(registration)), 201


# ── POST /events/<id>/register/<member_id> — admin registers a member ────────


@events_bp.post("/<int:event_id>/register/<int:member_id>")
@permission_required("events", "add_attendee", "Register member for event", allow=_own_event)
def register_member_for_event(event_id: int, member_id: int):
    body = request.get_json(silent=True) or {}
    try:
        data = RegisterSchema().load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    registration = EventService.register(
        event_id=event_id,
        member_id=member_id,
        notes=data.get("notes"),
        guests=data.get("guests", 0),
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(EventRegistrationSchema().dump(registration)), 201


# ── POST /events/<id>/cancel-registration — cancel own registration ──────────


@events_bp.post("/<int:event_id>/cancel-registration")
@permission_required("events", "register", "Register for events")
def cancel_registration(event_id: int):
    member_id = get_current_member().id
    registration = EventService.cancel_registration(event_id, member_id, own=True)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    if registration is None:  # was only on the attendee list
        return "", 204
    return jsonify(EventRegistrationSchema().dump(registration)), 200


# ── Registrations, and sign-ups waiting for approval ─────────────────────────


@events_bp.get("/<int:event_id>/registrations")
@permission_required("events", "add_attendee", "See and approve event sign-ups", allow=_own_event)
def list_registrations(event_id: int):
    status = request.args.get("status") or None
    registrations = EventService.registrations(event_id, status)
    return jsonify(EventRegistrationSchema(many=True).dump(registrations)), 200


@events_bp.post("/<int:event_id>/registrations/<int:member_id>/<any(approve, decline):decision>")
@permission_required("events", "add_attendee", "See and approve event sign-ups", allow=_own_event)
def decide_registration(event_id: int, member_id: int, decision: str):
    registration = EventService.decide(
        event_id, member_id, decision == "approve", get_current_member().id
    )
    db.session.commit()
    return jsonify(EventRegistrationSchema().dump(registration)), 200


# ── POST /events/<id>/attend/<member_id> — mark attendance ───────────────────


@events_bp.post("/<int:event_id>/attend/<int:member_id>")
@permission_required("events", "add_attendee", "Mark event attendance", allow=_own_event)
def mark_attendance(event_id: int, member_id: int):
    registration = EventService.mark_attendance(event_id, member_id)
    attendance.set_status(
        EventService.get(event_id), member_id, "present", get_current_member().id
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(EventRegistrationSchema().dump(registration)), 200


# ── Attendance roll of one event ─────────────────────────────────────────────


def _event_group(kwargs) -> int | None:
    """The group an event is for: a role held for that group (the team's
    trainer) may take its roll."""
    from hubra.core.models.event import ClubEvent

    event = db.session.get(ClubEvent, kwargs.get("event_id"))
    return event.group_id if event else None


@events_bp.get("/<int:event_id>/attendance")
@permission_required(
    "events", "add_attendee", "Mark event attendance", scope=_event_group
)
def get_roll(event_id: int):
    return jsonify(attendance.roll(EventService.get(event_id))), 200


@events_bp.put("/<int:event_id>/attendance")
@permission_required(
    "events", "add_attendee", "Mark event attendance", scope=_event_group
)
def save_roll(event_id: int):
    try:
        data = AttendanceRollSchema().load(request.get_json(silent=True) or {})
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)
    event = EventService.get(event_id)
    attendance.save_roll(event, data["entries"], get_current_member().id)
    db.session.commit()
    return jsonify(attendance.roll(event)), 200


# ── Attendance overview ──────────────────────────────────────────────────────


def _period() -> tuple[date, date]:
    """``from`` and ``to`` (ISO dates); by default this year until today."""
    today = date.today()
    try:
        since = date.fromisoformat(request.args.get("from") or f"{today.year}-01-01")
        until = date.fromisoformat(request.args.get("to") or today.isoformat())
    except ValueError:
        raise_error(400, "VALIDATION_ERROR", "Use ISO dates (YYYY-MM-DD) for from and to")
    return since, until


def _int_arg(name: str) -> int | None:
    value = request.args.get(name)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        raise_error(400, "VALIDATION_ERROR", f"{name} must be a number")


def _overview_response(group_id: int | None):
    from hubra.api.permissions import member_has_permission

    since, until = _period()
    data = attendance.overview(
        since,
        until,
        group_id=group_id,
        series_id=_int_arg("series_id"),
        category=request.args.get("category", "").strip(),
        type_=request.args.get("type", "").strip(),
    )
    if request.args.get("format") != "csv":
        return jsonify(data), 200
    # Birthdays (J+S needs them) only for those who may export members.
    with_birthday = member_has_permission(get_current_member(), "members.members.export")
    return Response(
        attendance.overview_csv(data, with_birthday),
        status=200,
        mimetype="text/csv",
        headers={
            "Content-Disposition": (
                f"attachment; filename=attendance-{since.isoformat()}-{until.isoformat()}.csv"
            )
        },
    )


@events_bp.get("/attendance")
@permission_required("events", "add_attendee", "Mark event attendance")
def attendance_overview():
    """Attendance per member over the events of a period (``?group_id``,
    ``series_id``, ``category``, ``type``; ``format=csv`` for a sheet)."""
    return _overview_response(_int_arg("group_id"))


@events_bp.get("/attendance/groups/<int:group_id>")
@permission_required(
    "events", "add_attendee", "Mark event attendance", scope="group_id"
)
def group_attendance(group_id: int):
    """The same for one group's events; a role held for that group is
    enough (a trainer of the team)."""
    return _overview_response(group_id)


@events_bp.get("/attendance/members/<int:member_id>")
@permission_required("events", "add_attendee", "Mark event attendance")
def member_attendance(member_id: int):
    since, until = _period()
    return jsonify(attendance.member_history(member_id, since, until)), 200


@events_bp.get("/attendance/me")
@permission_required("events", "read", "View events")
def my_attendance():
    since, until = _period()
    member = get_current_member()
    return jsonify(attendance.member_history(member.id, since, until)), 200


# ── GET /events/calendar — iCal format ───────────────────────────────────────


@events_bp.get("/calendar")
@permission_required("events", "read", "View events")
def calendar_export():
    """Export events as iCal format."""
    events = EventsService.list()
    ical_data = EventService.generate_ical(events)
    return Response(
        ical_data,
        status=200,
        mimetype="text/calendar",
        headers={"Content-Disposition": "attachment; filename=events.ics"},
    )


# ── Calendar subscription feed ───────────────────────────────────────────────
#
# Calendar apps cannot log in or send headers, so the feed URL carries a
# signed token with the club and the member. It stops working when the member
# is archived or disabled, the club is suspended, or the events module is
# switched off.


def _feed_serializer() -> URLSafeSerializer:
    return URLSafeSerializer(current_app.config["SECRET_KEY"], salt="calendar-feed")


@events_bp.get("/calendar/feed")
@require_member
def calendar_feed_link():
    """The member's personal calendar subscription URL."""
    return jsonify({"url": _feed_url(get_current_member())}), 200


@events_bp.post("/calendar/feed/renew")
@require_member
def renew_calendar_feed_link():
    """A new feed URL for the member; every older one stops working."""
    member = get_current_member()
    member.calendar_feed_version = (member.calendar_feed_version or 0) + 1
    db.session.commit()
    return jsonify({"url": _feed_url(member)}), 200


def _feed_url(member: Member) -> str:
    from hubra.core.tenant.context import current_tenant

    tenant = current_tenant()
    token = _feed_serializer().dumps(
        {
            "t": tenant.id if tenant else None,
            "m": member.id,
            "v": member.calendar_feed_version or 0,
        }
    )
    return url_for("events_bp.calendar_feed", token=token, _external=True)


@events_bp.get("/calendar/<token>.ics")
def calendar_feed(token: str):
    """Public iCalendar feed for calendar apps (token from /calendar/feed)."""
    from hubra.core.models.tenant import Tenant
    from hubra.core.modules import is_enabled
    from hubra.core.tenant.context import set_search_path

    try:
        data = _feed_serializer().loads(token)
    except BadSignature:
        return api_error("NOT_FOUND", "Unknown calendar", 404)

    tenant = None
    if data.get("t") is not None:
        tenant = db.session.get(Tenant, data["t"])
        if tenant is None or tenant.status != "active":
            return api_error("NOT_FOUND", "Unknown calendar", 404)
        g.tenant = tenant
        set_search_path(tenant.id)
    if not is_enabled("events"):
        return api_error("NOT_FOUND", "Unknown calendar", 404)
    member = db.session.get(Member, data.get("m"))
    if member is None or member.archived_at is not None or member.is_blocked:
        return api_error("NOT_FOUND", "Unknown calendar", 404)
    if data.get("v", 0) != (member.calendar_feed_version or 0):
        return api_error("NOT_FOUND", "Unknown calendar", 404)  # renewed since

    # The last 90 days and everything ahead.
    since = (date.today() - timedelta(days=90)).isoformat()
    ical = EventService.generate_ical(
        EventsService.list(from_str=since), name=tenant.name if tenant else None
    )
    return Response(
        ical,
        status=200,
        mimetype="text/calendar",
        headers={"Cache-Control": "private, max-age=900"},
    )
