"""Recurring events: a weekly rule whose dates are ordinary events.

A series (``EventSeries``) holds the rule; each date is a ``ClubEvent`` with
``series_id`` and ``series_date``, so sign-ups, places and attendance work
per date as for any event. Edits and deletes take a scope: ``this`` (the one
date) or ``following`` (this date and all later ones in the series).
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from hubra.api.utils import log_audit
from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.event import (
    ClubEvent,
    EventAttendance,
    EventRegistration,
    EventSeries,
)

# A rule may not run on for ever; two seasons of two trainings a week fit.
MAX_OCCURRENCES = 400
MAX_YEARS = 3

# The fields a new date copies from the one it is made from.
_COPIED = (
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
    "cover_image_url",
    "color",
    "group_id",
    "created_by",
)
# Fields that move each date, so they cannot be set for all following dates.
_PER_DATE = ("date", "end_date")


def rule_dates(
    start: date,
    until: date,
    weekdays: list[int],
    interval: int = 1,
    skip: list[str] | tuple[str, ...] = (),
) -> list[date]:
    """The dates of a weekly rule from ``start`` to ``until`` (both included).

    Every ``interval``-th week counts, from the week ``start`` is in; within
    it, the given weekdays (Monday 0). Dates in ``skip`` are left out.
    """
    skipped = set(skip)
    week0 = start - timedelta(days=start.weekday())
    days = set(weekdays)
    out = []
    d = start
    while d <= until:
        if (
            d.weekday() in days
            and ((d - week0).days // 7) % interval == 0
            and d.isoformat() not in skipped
        ):
            out.append(d)
        d += timedelta(days=1)
    return out


def check_rule(start: date, rule: dict) -> list[date]:
    """Validate a recurrence (``until``, ``weekdays``, ``interval``,
    ``skip_dates``) starting at ``start``; return its dates."""
    until = rule["until"]
    if until < start:
        raise_error(400, "VALIDATION_ERROR", "until is before the first date")
    if until > start + timedelta(days=366 * MAX_YEARS):
        raise_error(
            400,
            "VALIDATION_ERROR",
            f"A series can run for at most {MAX_YEARS} years",
        )
    dates = rule_dates(
        start,
        until,
        rule.get("weekdays") or [start.weekday()],
        rule.get("interval") or 1,
        [d.isoformat() for d in rule.get("skip_dates") or ()],
    )
    if not dates:
        raise_error(400, "VALIDATION_ERROR", "The rule gives no dates")
    if len(dates) > MAX_OCCURRENCES:
        raise_error(
            400,
            "VALIDATION_ERROR",
            f"A series can have at most {MAX_OCCURRENCES} dates",
        )
    return dates


def _copy(template: ClubEvent, on: date, series: EventSeries) -> ClubEvent:
    """A new date of the series, like ``template`` (deadlines and the end
    date move along with the date)."""
    shift = on - template.date
    event = ClubEvent(**{f: getattr(template, f) for f in _COPIED})
    event.date = on
    event.end_date = template.end_date + shift if template.end_date else None
    event.registration_deadline = (
        template.registration_deadline + shift
        if template.registration_deadline
        else None
    )
    event.cancellation_deadline = (
        template.cancellation_deadline + shift
        if template.cancellation_deadline
        else None
    )
    event.series_id = series.id
    event.series_date = on
    db.session.add(event)
    return event


def create_series(first: ClubEvent, rule: dict, actor_id: int) -> EventSeries:
    """Turn a new event into the first date of a series and add the others.

    ``first`` is flushed and dated on the rule's start; a first date that
    the rule leaves out (a Monday event with a Tuesday rule) is moved to
    the rule's first date.
    """
    dates = check_rule(first.date, rule)
    series = EventSeries(
        start_date=first.date,
        until=rule["until"],
        interval=rule.get("interval") or 1,
        weekdays=sorted(set(rule.get("weekdays") or [first.date.weekday()])),
        skip_dates=sorted({d.isoformat() for d in rule.get("skip_dates") or ()}),
        created_by=actor_id,
    )
    db.session.add(series)
    db.session.flush()
    if dates[0] != first.date:
        shift = dates[0] - first.date
        for field in ("end_date", "registration_deadline", "cancellation_deadline"):
            if getattr(first, field) is not None:
                setattr(first, field, getattr(first, field) + shift)
        first.date = dates[0]
        series.start_date = dates[0]
    first.series_id = series.id
    first.series_date = first.date
    for on in dates[1:]:
        _copy(first, on, series)
    db.session.flush()
    return series


def _has_attendance(event_id: int) -> bool:
    """Whether anything was recorded on the date that a delete would lose."""
    return (
        db.session.scalar(
            select(EventAttendance.id).where(EventAttendance.event_id == event_id).limit(1)
        )
        is not None
        or db.session.scalar(
            select(EventRegistration.id)
            .where(
                EventRegistration.event_id == event_id,
                EventRegistration.status == "attended",
            )
            .limit(1)
        )
        is not None
    )


def following(event: ClubEvent) -> list[ClubEvent]:
    """This date of the series and all later ones, in date order."""
    return list(
        db.session.scalars(
            select(ClubEvent)
            .where(
                ClubEvent.series_id == event.series_id,
                ClubEvent.series_date >= event.series_date,
            )
            .order_by(ClubEvent.series_date, ClubEvent.id)
        ).all()
    )


def _tell_once(events: list[ClubEvent], title: str, skip_member_id: int) -> None:
    """One notification per member for a change to several upcoming dates
    (not one for each training they signed up for)."""
    from hubra.api.events.services import _OPEN
    from hubra.api.notifications.services import notify_member

    today = date.today()
    told: set[int] = set()
    upcoming = [e for e in events if (e.end_date or e.date) >= today]
    if not upcoming:
        return
    for reg in db.session.scalars(
        select(EventRegistration).where(
            EventRegistration.event_id.in_([e.id for e in upcoming]),
            EventRegistration.status.in_(_OPEN),
        )
    ).all():
        if reg.member_id in told or reg.member_id == skip_member_id:
            continue
        told.add(reg.member_id)
        notify_member(reg.member_id, "info", title, upcoming[0].title)


def update_following(
    event: ClubEvent, data: dict, rule: dict | None, actor_id: int
) -> ClubEvent:
    """Change this date and all later ones of its series.

    Field changes go to every following date (moved dates keep their own
    date). A new ``rule`` splits the series here: the earlier dates keep the
    old rule, ending the day before; from here on the new rule applies,
    dates it no longer has are removed (or kept outside the series when
    attendance was taken), and new ones are added. Returns this date, or
    the new rule's first date when this one is gone.
    """
    from hubra.api.events.services import EventService

    if event.series_id is None:
        raise_error(400, "NOT_A_SERIES", "This event is not part of a series")
    moved = [f for f in _PER_DATE if f in data]
    if moved:
        raise_error(
            400,
            "VALIDATION_ERROR",
            "date and end_date change one date at a time; change the rule "
            "to move the series",
        )
    series = event.series
    dates = following(event)
    for occ in dates:
        EventService.update(occ, data, actor_id, quiet=True, audit=False)

    if rule is not None:
        start = event.series_date
        new_dates = check_rule(start, rule)
        if start != series.start_date:
            # Split: the dates before keep the old rule.
            series.until = start - timedelta(days=1)
            series = EventSeries(
                created_by=actor_id,
                start_date=start,
                until=rule["until"],
                weekdays=[start.weekday()],
                skip_dates=[],
            )
            db.session.add(series)
            db.session.flush()
            for occ in dates:
                occ.series_id = series.id
        series.start_date = start
        series.until = rule["until"]
        series.interval = rule.get("interval") or 1
        series.weekdays = sorted(set(rule.get("weekdays") or [start.weekday()]))
        series.skip_dates = sorted(
            {d.isoformat() for d in rule.get("skip_dates") or ()}
        )
        wanted = set(new_dates)
        by_date = {occ.series_date: occ for occ in dates}
        template = event
        gone = []
        for on, occ in by_date.items():
            if on in wanted:
                continue
            if _has_attendance(occ.id):
                occ.series_id = None
                occ.series_date = None
            else:
                gone.append(occ)
        if template in gone:
            template = next((o for o in dates if o not in gone), event)
        db.session.flush()
        for on in new_dates:
            if on not in by_date:
                _copy(template, on, series)
        _tell_once(gone, "Event cancelled", actor_id)
        for occ in gone:
            db.session.delete(occ)
        db.session.flush()
        if event in gone:
            # This date is no longer in the rule: answer with the first
            # date of the new rule instead.
            event = db.session.scalar(
                select(ClubEvent)
                .where(ClubEvent.series_id == series.id)
                .order_by(ClubEvent.series_date)
                .limit(1)
            )
            dates = following(event)

    _tell_once(dates, "Event changed", actor_id)
    log_audit(
        actor_id=actor_id,
        action="update_event_series",
        target_type="Event",
        target_id=event.id,
        target_label=event.title,
    )
    return event


def delete_one(event: ClubEvent) -> None:
    """Delete one date: the rule leaves it out from now on."""
    series = event.series
    if series is not None and event.series_date is not None:
        series.skip_dates = sorted(
            set(series.skip_dates or ()) | {event.series_date.isoformat()}
        )


def delete_following(event: ClubEvent, actor_id: int) -> None:
    """Delete this date and all later ones; the series ends the day before
    (and goes when no date is left)."""
    if event.series_id is None:
        raise_error(400, "NOT_A_SERIES", "This event is not part of a series")
    series = event.series
    dates = following(event)
    _tell_once(dates, "Event cancelled", actor_id)
    for occ in dates:
        db.session.delete(occ)
    db.session.flush()
    series.until = event.series_date - timedelta(days=1)
    left = db.session.scalar(
        select(ClubEvent.id).where(ClubEvent.series_id == series.id).limit(1)
    )
    if left is None:
        db.session.delete(series)
    log_audit(
        actor_id=actor_id,
        action="delete_event_series",
        target_type="Event",
        target_id=event.id,
        target_label=event.title,
    )
