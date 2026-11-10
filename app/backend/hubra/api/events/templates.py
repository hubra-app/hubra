"""Event templates (roadmap idea 15): save an event's place, times,
capacity, settings and description under a name, and start new events
from it ("Neu aus Vorlage"). The date, deadlines and sign-ups stay with the
event; ``days`` keeps the length of a multi-day event."""

from __future__ import annotations

from sqlalchemy import select

from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.event import ClubEvent, EventTemplate
from hubra.core.utils import log_audit

# The event fields a template keeps (as the create endpoint names them).
FIELDS = (
    "title",
    "time",
    "location",
    "type",
    "description",
    "meeting_url",
    "all_day",
    "category",
    "max_attendees",
    "requires_approval",
    "is_public",
    "federation_shared",
    "trial_spots",
    "cover_image_url",
    "color",
    "group_id",
)
NAME_MAX = 255


def from_event(event: ClubEvent) -> dict:
    data = {field: getattr(event, field) for field in FIELDS}
    if event.end_date and event.end_date > event.date:
        data["days"] = (event.end_date - event.date).days
    return data


def to_dict(template: EventTemplate) -> dict:
    return {
        "id": template.id,
        "name": template.name,
        "data": template.data or {},
        "created_by": template.created_by,
        "created_at": template.created_at.isoformat() if template.created_at else None,
    }


def list_templates() -> list[EventTemplate]:
    return list(
        db.session.scalars(
            select(EventTemplate).order_by(db.func.lower(EventTemplate.name))
        ).all()
    )


def save(event_id: int, name: str, actor_id: int) -> EventTemplate:
    event = db.session.get(ClubEvent, event_id)
    if event is None:
        raise_error(404, "NOT_FOUND", f"Event {event_id} not found")
    name = (name or "").strip() or event.title
    if len(name) > NAME_MAX:
        raise_error(400, "VALIDATION_ERROR", "The name is too long")
    template = EventTemplate(name=name, data=from_event(event), created_by=actor_id)
    db.session.add(template)
    db.session.flush()
    log_audit(
        actor_id=actor_id,
        action="create_event_template",
        target_type="EventTemplate",
        target_id=template.id,
        target_label=template.name,
    )
    return template


def delete(template_id: int, actor_id: int) -> None:
    template = db.session.get(EventTemplate, template_id)
    if template is None:
        raise_error(404, "NOT_FOUND", f"Template {template_id} not found")
    log_audit(
        actor_id=actor_id,
        action="delete_event_template",
        target_type="EventTemplate",
        target_id=template.id,
        target_label=template.name,
    )
    db.session.delete(template)
