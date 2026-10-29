"""Events blueprint — CRUD and attendee management."""

from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, Response, current_app, g, jsonify, request, url_for
from itsdangerous import BadSignature, URLSafeSerializer
from hubra.api.auth.helpers import get_current_member
from marshmallow import ValidationError
from hubra.api.permissions import permission_required, require_member
from hubra.core.errors import api_error, raise_error
from hubra.core.extensions import db
from hubra.core.models.member import Member
from hubra.core.schemas.event import (
    ClubEventCreateSchema,
    ClubEventSchema,
    ClubEventUpdateSchema,
    EventRegistrationSchema,
    RegisterSchema,
)
from hubra.api.events.services import EventService, EventsService

events_bp = Blueprint("events_bp", __name__)

_event_schema = ClubEventSchema()
_events_schema = ClubEventSchema(many=True)
_create_schema = ClubEventCreateSchema()
_update_schema = ClubEventUpdateSchema()


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
@permission_required("events", "update", "Update events")
def update_event(event_id: int):
    event = EventService.get(event_id)

    body = request.get_json(silent=True) or {}
    try:
        data = _update_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

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
@permission_required("events", "delete", "Delete events")
def delete_event(event_id: int):
    EventService.delete(event_id, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── POST /events/<id>/attendees/<member_id> ───────────────────────────────────


@events_bp.post("/<int:event_id>/attendees/<int:member_id>")
@permission_required("events", "add_attendee", "Add event attendee")
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
@permission_required("events", "remove_attendee", "Remove event attendee")
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
@permission_required("events", "add_attendee", "Register member for event")
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


# ── POST /events/<id>/attend/<member_id> — mark attendance ───────────────────


@events_bp.post("/<int:event_id>/attend/<int:member_id>")
@permission_required("events", "add_attendee", "Mark event attendance")
def mark_attendance(event_id: int, member_id: int):
    registration = EventService.mark_attendance(event_id, member_id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(EventRegistrationSchema().dump(registration)), 200


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
    from hubra.core.tenant.context import current_tenant

    tenant = current_tenant()
    token = _feed_serializer().dumps(
        {"t": tenant.id if tenant else None, "m": get_current_member().id}
    )
    url = url_for("events_bp.calendar_feed", token=token, _external=True)
    return jsonify({"url": url}), 200


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
