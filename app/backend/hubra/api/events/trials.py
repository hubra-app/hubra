"""Trial trainings: people who aren't members yet book a training to try.

An event with ``trial_spots`` shows on the club's public trial page (on the
join portal, ``/clubs/<slug>/trial``). A booking counts once the person
opened the link in the mail we send, which also proves the address; the
same link cancels it. Whoever runs trials (``events.trials.manage``) sees
the bookings, marks who came, and invites someone as a trial member with
one click (the usual club invite, with status and membership type
``trial``).
"""

from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta, timezone

from flask import jsonify, request
from sqlalchemy import func, select

from hubra.api.events.routes import _public_club, events_bp
from hubra.core.auth import api_tokens
from hubra.core.utils import log_audit
from hubra.core.auth.helpers import get_current_member
from hubra.core.errors import api_error, raise_error
from hubra.core.extensions import db, limiter
from hubra.core.models.event import ClubEvent, TrialSignup
from hubra.core.models.member import Member
from hubra.core.permissions import member_has_permission, permission_required

# How far ahead the trial page lists trainings.
TRIAL_DAYS_AHEAD = 60
# An unconfirmed booking holds its place this long, then frees it.
PENDING_HOLD = timedelta(hours=24)
# Bookings the club no longer needs are deleted by a daily job
# (hubra.core.tasks.reminder_tasks.purge_trial_signups_task).
MANAGE_KEY = "events.trials.manage"
# Inviting someone to join is a members right, also from the trial list.
INVITE_KEY = "members.members.create"

# "invited" too: someone asked to join before the training still comes to it.
_TAKING = ("confirmed", "attended", "invited")
_STATUSES = ("confirmed", "attended", "no_show", "cancelled")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def places_taken(event_id: int, excluding: int | None = None) -> int:
    """Confirmed bookings, and unconfirmed ones still holding their place
    (without the booking *excluding*)."""
    since = _now() - PENDING_HOLD
    query = select(func.count(TrialSignup.id)).where(
        TrialSignup.event_id == event_id,
        (TrialSignup.status.in_(_TAKING))
        | ((TrialSignup.status == "pending") & (TrialSignup.created_at >= since)),
    )
    if excluding is not None:
        query = query.where(TrialSignup.id != excluding)
    return int(db.session.scalar(query) or 0)


def _lock_event(event_id: int) -> None:
    """One booking at a time per event, so two people don't take the last place."""
    db.session.execute(
        select(ClubEvent.id).where(ClubEvent.id == event_id).with_for_update()
    )


def _trial_events() -> list[ClubEvent]:
    today = date.today()
    return list(
        db.session.scalars(
            select(ClubEvent)
            .where(
                ClubEvent.trial_spots.is_not(None),
                ClubEvent.trial_spots > 0,
                ClubEvent.date >= today,
                ClubEvent.date <= today + timedelta(days=TRIAL_DAYS_AHEAD),
            )
            .order_by(ClubEvent.date, ClubEvent.time, ClubEvent.id)
            .limit(100)
        )
    )


def _public_event(event: ClubEvent) -> dict:
    return {
        "id": event.id,
        "title": event.title,
        "date": event.date.isoformat(),
        "time": None if event.all_day else event.time,
        "location": event.location,
        "description": event.description,
        "category": event.category,
        "free": max(0, (event.trial_spots or 0) - places_taken(event.id)),
    }


def _by_token(token: str) -> TrialSignup | None:
    if not token or len(token) > 64:
        return None
    return db.session.scalar(select(TrialSignup).where(TrialSignup.token == token))


def _booking(signup: TrialSignup) -> dict:
    return {
        "status": signup.status,
        "firstName": signup.first_name,
        "event": _public_event(signup.event),
    }


def _mail_locale(lang: str | None) -> str:
    return "en-GB" if (lang or "").lower().startswith("en") else "de-CH"


def _send_confirm(signup: TrialSignup, slug: str, lang: str | None) -> None:
    from hubra.core.services.email import (
        _get_sso_base_url,
        _send,
        club_display_name,
    )
    from hubra.core.services.mail_i18n import render_mail_template

    event = signup.event
    link = f"{_get_sso_base_url()}/clubs/{slug}/trial?token={signup.token}"
    when = event.date.strftime("%d.%m.%Y") + (
        f", {event.time}" if event.time and not event.all_day else ""
    )
    html, text, subject = render_mail_template(
        "trial_confirm",
        locale=_mail_locale(lang),
        name=signup.first_name,
        club_name=club_display_name(),
        event_title=event.title,
        when=when,
        location=event.location or "",
        confirm_url=link,
    )
    _send(signup.email, signup.name, subject, html, text)


def _tell_staff(signup: TrialSignup) -> None:
    """A bell notification for whoever runs trials (and the event's creator)."""
    from hubra.core.notifications.services import notify_member

    event = signup.event
    members = db.session.scalars(
        select(Member).where(Member.status == "active", Member.archived_at.is_(None))
    ).all()
    title = f"Trial training: {signup.name}"
    msg = f"{event.title}, {event.date.strftime('%d.%m.%Y')}"
    link = "/app/operations/events/trials"
    for member in members:
        if member.id == event.created_by or member_has_permission(member, MANAGE_KEY):
            notify_member(member.id, "info", title, msg, link, topic="events")


def _plausible_email(email: str) -> bool:
    """One @, something before it, a dot inside the domain, no spaces.

    Plain string checks: a regex with nested + on someone's input can take
    polynomial time (CodeQL py/polynomial-redos).
    """
    if any(c.isspace() for c in email) or email.count("@") != 1:
        return False
    local, domain = email.split("@")
    return bool(local) and "." in domain.strip(".") and not domain.startswith(".")


def _clean(text, limit: int) -> str | None:
    text = str(text or "").strip()
    return text[:limit] or None


# ── The public trial page ─────────────────────────────────────────────────────


@events_bp.get("/public/<string:slug>/trials")
@limiter.limit("60 per minute")
def public_trials(slug: str):
    """The trainings someone who isn't a member may book to try."""
    tenant = _public_club(slug)
    if tenant is None:
        return api_error("NOT_FOUND", "Unknown club", 404)
    # Read by the join portal with its credentials, so the usual CORS
    # (CORS_ORIGINS) applies, not the any-site header of the public events.
    resp = jsonify(
        {
            "club": {"name": tenant.name, "slug": tenant.slug},
            "events": [_public_event(e) for e in _trial_events()],
        }
    )
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _address_key() -> str:
    """Rate-limit key for the booking mails: the address they go to."""
    data = request.get_json(silent=True) or {}
    email = str(data.get("email") or "").strip().lower()[:255]
    return f"trial-mail:{email}"


@events_bp.post("/public/<string:slug>/trials")
@limiter.limit("10 per hour")
# Per address, whatever the IP: booking mails can't be used to flood
# someone's inbox from many machines.
@limiter.limit("5 per day", key_func=_address_key)
def public_trial_signup(slug: str):
    """Book a trial training. It counts once the address is confirmed."""
    tenant = _public_club(slug)
    if tenant is None:
        return api_error("NOT_FOUND", "Unknown club", 404)
    data = request.get_json(silent=True) or {}
    # A field people don't see: a bot that fills it gets a polite answer
    # and nothing is stored.
    if str(data.get("website") or "").strip():
        return jsonify({"status": "pending"}), 201

    first = _clean(data.get("firstName"), 100)
    last = _clean(data.get("lastName"), 100)
    email = (_clean(data.get("email"), 255) or "").lower()
    if not first or not last:
        raise_error(400, "VALIDATION_ERROR", "First and last name are required")
    if not _plausible_email(email):
        raise_error(400, "VALIDATION_ERROR", "A valid email address is required")
    if data.get("consent") is not True:
        raise_error(400, "VALIDATION_ERROR", "Consent is required")
    birth = None
    if data.get("birthDate"):
        try:
            birth = date.fromisoformat(str(data["birthDate"]))
        except ValueError:
            raise_error(400, "VALIDATION_ERROR", "birthDate must be YYYY-MM-DD")
        if not date(1900, 1, 1) <= birth <= date.today():
            raise_error(400, "VALIDATION_ERROR", "birthDate is out of range")

    try:
        event_id = int(data.get("eventId"))
    except (TypeError, ValueError):
        raise_error(400, "VALIDATION_ERROR", "eventId is required")
    event = next((e for e in _trial_events() if e.id == event_id), None)
    if event is None:
        raise_error(404, "NOT_FOUND", "This training takes no trial bookings")

    _lock_event(event.id)
    taken = db.session.scalar(
        select(TrialSignup).where(
            TrialSignup.event_id == event.id,
            func.lower(TrialSignup.email) == email,
            TrialSignup.status != "cancelled",
        )
    )
    if taken is not None:
        # Lost the mail: send the booking's link again instead of a second
        # booking. The answer is the same as for a new booking, so the form
        # doesn't tell anyone whether an address booked a training.
        if taken.status in ("pending", "confirmed"):
            _send_confirm(taken, tenant.slug, data.get("lang"))
        return jsonify({"status": "pending"}), 201
    if places_taken(event.id) >= (event.trial_spots or 0):
        raise_error(409, "EVENT_FULL", "No trial places left for this training")

    signup = TrialSignup(
        event_id=event.id,
        first_name=first,
        last_name=last,
        email=email,
        phone=_clean(data.get("phone"), 50),
        birth_date=birth,
        message=_clean(data.get("message"), 2000),
        token=secrets.token_urlsafe(32),
        status="pending",
    )
    db.session.add(signup)
    db.session.flush()
    db.session.refresh(signup)
    db.session.commit()
    _send_confirm(signup, tenant.slug, data.get("lang"))
    return jsonify({"status": "pending"}), 201


@events_bp.post("/public/<string:slug>/trials/confirm")
@limiter.limit("30 per hour")
def public_trial_confirm(slug: str):
    """The link in the mail: the booking counts from now on."""
    tenant = _public_club(slug)
    if tenant is None:
        return api_error("NOT_FOUND", "Unknown club", 404)
    signup = _by_token(str((request.get_json(silent=True) or {}).get("token") or ""))
    if signup is None:
        return api_error("NOT_FOUND", "Unknown or expired link", 404)
    if signup.status == "pending":
        # A booking confirmed after its hold ran out lost its place in the
        # meantime: it only counts if one is still free (and the training
        # still takes trials).
        _lock_event(signup.event_id)
        event = signup.event
        if places_taken(event.id, excluding=signup.id) >= (event.trial_spots or 0):
            db.session.rollback()
            return api_error(
                "EVENT_FULL", "No trial places left for this training", 409
            )
        signup.status = "confirmed"
        signup.confirmed_at = _now()
        _tell_staff(signup)
        db.session.commit()
    return jsonify(_booking(signup)), 200


@events_bp.post("/public/<string:slug>/trials/cancel")
@limiter.limit("30 per hour")
def public_trial_cancel(slug: str):
    """The person can't come after all: the place is free again."""
    tenant = _public_club(slug)
    if tenant is None:
        return api_error("NOT_FOUND", "Unknown club", 404)
    signup = _by_token(str((request.get_json(silent=True) or {}).get("token") or ""))
    if signup is None:
        return api_error("NOT_FOUND", "Unknown or expired link", 404)
    if signup.status in ("pending", "confirmed"):
        signup.status = "cancelled"
        db.session.commit()
    return jsonify(_booking(signup)), 200


# ── For the trainers ──────────────────────────────────────────────────────────


def _dump(signup: TrialSignup) -> dict:
    event = signup.event
    return {
        "id": signup.id,
        "eventId": signup.event_id,
        "eventTitle": event.title,
        "eventDate": event.date.isoformat(),
        "eventTime": None if event.all_day else event.time,
        "firstName": signup.first_name,
        "lastName": signup.last_name,
        "email": signup.email,
        "phone": signup.phone,
        "birthDate": signup.birth_date.isoformat() if signup.birth_date else None,
        "message": signup.message,
        "status": signup.status,
        "createdAt": signup.created_at.isoformat(),
        "confirmedAt": signup.confirmed_at.isoformat() if signup.confirmed_at else None,
        "invitedAt": signup.invited_at.isoformat() if signup.invited_at else None,
    }


@events_bp.get("/trials")
@permission_required("trials", "read", "View trial trainings")
def list_trials():
    """Trial bookings: upcoming by default, ``?past=1`` for the last months."""
    past = request.args.get("past") in ("1", "true")
    today = date.today()
    query = select(TrialSignup).join(ClubEvent).where(TrialSignup.status != "pending")
    if past:
        query = query.where(ClubEvent.date < today).order_by(ClubEvent.date.desc())
    else:
        query = query.where(ClubEvent.date >= today).order_by(ClubEvent.date)
    signups = db.session.scalars(query.order_by(TrialSignup.id).limit(500)).all()
    return jsonify(
        {
            "trials": [_dump(s) for s in signups],
            "events": [
                {
                    "id": e.id,
                    "title": e.title,
                    "date": e.date.isoformat(),
                    "spots": e.trial_spots,
                    "taken": places_taken(e.id),
                }
                for e in _trial_events()
            ],
        }
    ), 200


def _get(signup_id: int) -> TrialSignup:
    signup = db.session.get(TrialSignup, signup_id)
    if signup is None or signup.status == "pending":
        raise_error(404, "NOT_FOUND", "No such trial booking")
    return signup


@events_bp.patch("/trials/<int:signup_id>")
@permission_required("trials", "manage", "Manage trial trainings")
def update_trial(signup_id: int):
    """Mark who came (attended, no_show), or cancel a booking."""
    signup = _get(signup_id)
    status = (request.get_json(silent=True) or {}).get("status")
    if status not in _STATUSES:
        raise_error(400, "VALIDATION_ERROR", f"status must be one of {_STATUSES}")
    if signup.status == "invited":
        raise_error(409, "ALREADY_INVITED", "This person was already invited")
    signup.status = status
    db.session.commit()
    return jsonify(_dump(signup)), 200


@events_bp.post("/trials/<int:signup_id>/invite")
@permission_required("trials", "manage", "Manage trial trainings")
def invite_trial(signup_id: int):
    """Invite the person to join as a trial member (the usual invite mail)."""
    from hubra.api.members.services import MembersService

    actor = get_current_member()
    # Running trials doesn't make someone a member admin: the invite needs
    # the same right as an invite from the member list.
    refusal = api_tokens.club_scope_refusal(actor, INVITE_KEY)
    if refusal is not None:
        return refusal
    if not member_has_permission(actor, INVITE_KEY):
        raise_error(
            403, "FORBIDDEN", "Inviting members needs the right to create members"
        )
    signup = _get(signup_id)
    if signup.status == "invited":
        raise_error(409, "ALREADY_INVITED", "This person was already invited")
    MembersService.invite(
        {
            "email": signup.email,
            "first_name": signup.first_name,
            "last_name": signup.last_name,
            "status": "trial",
            "membership_type": "trial",
        },
        actor.id if actor else None,
    )
    signup.status = "invited"
    signup.invited_at = _now()
    db.session.commit()
    return jsonify(_dump(signup)), 200


@events_bp.delete("/trials/<int:signup_id>")
@permission_required("trials", "manage", "Manage trial trainings")
def delete_trial(signup_id: int):
    """Remove a booking and the person's details (on request, or by mistake)."""
    signup = db.session.get(TrialSignup, signup_id)
    if signup is None:
        return api_error("NOT_FOUND", "No such trial booking", 404)
    actor = get_current_member()
    log_audit(
        actor_id=actor.id if actor else None,
        action="delete_trial_signup",
        target_type="TrialSignup",
        target_id=signup.id,
        target_label=signup.event.title,
    )
    db.session.delete(signup)
    db.session.commit()
    return "", 204
