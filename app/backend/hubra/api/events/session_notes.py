"""Session notes on event dates (roadmap idea 13).

Per date a trainer notes what was trained (members of the event may read
it), a note for the next trainer (only those who take attendance see it)
and a link to a guide. The next date of the same series shows the last
notes before it, so whoever trains next knows where the group is.
"""

from __future__ import annotations

from flask import jsonify, request
from sqlalchemy import select

from hubra.api.events.routes import _event_group, events_bp
from hubra.api.events.services import EventService
from hubra.core.auth.helpers import get_current_member
from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.event import ClubEvent, EventSessionNote
from hubra.core.models.member import Member
from hubra.core.permissions import (
    _current_member,
    member_has_permission,
    permission_required,
    scoped_permission_keys,
)

TEXT_MAX = 4000
URL_MAX = 500
_TRAINER = "events.events.add_attendee"


def _text(body: dict, key: str) -> str | None:
    value = body.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise_error(400, "VALIDATION_ERROR", f"{key} is text", {key: ["Text"]})
    value = value.strip()
    if len(value) > TEXT_MAX:
        raise_error(
            400,
            "VALIDATION_ERROR",
            f"{key} is at most {TEXT_MAX} characters",
            {key: [f"At most {TEXT_MAX} characters"]},
        )
    return value or None


def _url(value) -> str | None:
    """A web link (https://) or a page in the app (/app/...)."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise_error(400, "VALIDATION_ERROR", "guide_url is text")
    value = value.strip()
    if not value:
        return None
    ok = value.startswith("https://") or (
        value.startswith("/") and not value.startswith("//")
    )
    if not ok or len(value) > URL_MAX or any(c.isspace() for c in value):
        raise_error(
            400,
            "VALIDATION_ERROR",
            "guide_url is an https:// link or a page in the app (/app/...)",
            {"guide_url": ["https:// or /app/..."]},
        )
    return value


def is_trainer(event: ClubEvent) -> bool:
    """Who takes attendance for this event (club-wide or for its group)."""
    member = _current_member()
    if member_has_permission(member, _TRAINER):
        return True
    if event.group_id is None:
        return False
    return _TRAINER in set(scoped_permission_keys(member).get(event.group_id, ()))


def _note(event_id: int) -> EventSessionNote | None:
    return db.session.scalar(
        select(EventSessionNote).where(EventSessionNote.event_id == event_id)
    )


def _dump(note: EventSessionNote | None, *, trainer: bool, event=None) -> dict | None:
    if note is None:
        return None
    by = db.session.get(Member, note.updated_by) if note.updated_by else None
    out = {
        "trained": note.trained,
        "guide_url": note.guide_url,
        "updated_at": note.updated_at.isoformat(),
        "updated_by_name": by.name if by else None,
    }
    if trainer:
        out["trainer_note"] = note.trainer_note
    if event is not None:
        out["event_id"] = event.id
        out["date"] = event.date.isoformat()
    return out


def previous(event: ClubEvent) -> tuple[ClubEvent, EventSessionNote] | None:
    """The last notes on an earlier date of the same series."""
    if event.series_id is None:
        return None
    row = db.session.execute(
        select(ClubEvent, EventSessionNote)
        .join(EventSessionNote, EventSessionNote.event_id == ClubEvent.id)
        .where(
            ClubEvent.series_id == event.series_id,
            ClubEvent.date < event.date,
            ClubEvent.id != event.id,
        )
        .order_by(ClubEvent.date.desc())
        .limit(1)
    ).first()
    return (row[0], row[1]) if row else None


def view(event: ClubEvent) -> dict:
    trainer = is_trainer(event)
    before = previous(event)
    return {
        "note": _dump(_note(event.id), trainer=trainer),
        "previous": _dump(before[1], trainer=trainer, event=before[0])
        if before
        else None,
        "can_edit": trainer,
    }


def save(event: ClubEvent, body: dict, actor_id: int) -> None:
    trained = _text(body, "trained")
    trainer_note = _text(body, "trainer_note")
    guide_url = _url(body.get("guide_url"))
    note = _note(event.id)
    if not (trained or trainer_note or guide_url):
        if note is not None:
            db.session.delete(note)
        return
    if note is None:
        note = EventSessionNote(event_id=event.id)
        db.session.add(note)
    note.trained = trained
    note.trainer_note = trainer_note
    note.guide_url = guide_url
    note.updated_by = actor_id


# ── Routes ───────────────────────────────────────────────────────────────────


@events_bp.get("/<int:event_id>/session-notes")
@permission_required("events", "read", "View events")
def get_session_notes(event_id: int):
    """This date's notes and the last ones of the series before it; the
    trainer note only for those who take attendance."""
    return jsonify(view(EventService.get(event_id))), 200


@events_bp.put("/<int:event_id>/session-notes")
@permission_required(
    "events", "add_attendee", "Mark event attendance", scope=_event_group
)
def put_session_notes(event_id: int):
    """``{trained?, trainer_note?, guide_url?}``; all empty removes the notes."""
    event = EventService.get(event_id)
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise_error(400, "VALIDATION_ERROR", "Send an object")
    save(event, body, get_current_member().id)
    db.session.commit()
    return jsonify(view(event)), 200
