"""Reminders before an event starts and before a poll closes.

Every quarter of an hour the scheduler looks, per club, for events that
start and polls that close within the club's reminder window (the module
setting ``reminder_hours``, 24 unless changed; 0 switches it off). Each
event and poll gets one reminder: an in-app notification for everyone it
concerns, a mail for those with a verified address who did not switch the
mail off, and ``event.reminder`` / ``poll.closing`` for other modules.

An event or poll created inside the window gets none: its members were
just told about it.
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from hubra.core.extensions import db
from hubra.core.modules import emit, get_config, per_tenant_job
from hubra.core.modules.events import EVENT_REMINDER, POLL_CLOSING
from hubra.core.services.email import DEFAULT_LANG
from hubra.core.services.mail_format import mail_date
from hubra.core.services.mail_i18n import render_mail_template
from hubra.core.tasks import celery_app

logger = logging.getLogger(__name__)

DEFAULT_TZ = "Europe/Zurich"
# All-day events (and those without a start time) count as starting at
# nine, so their reminder does not go out at midnight.
ALL_DAY_START = time(9, 0)
# Registrations that hold a place.
_ATTENDING = ("registered", "approved")


def club_zone() -> ZoneInfo:
    """The club's time zone (Settings › Verein), Zurich by default."""
    from hubra.core.tenant.context import current_tenant

    tenant = current_tenant()
    name = ((tenant.settings or {}).get("branding") or {}).get(
        "timezone"
    ) if tenant else None
    try:
        return ZoneInfo(name or DEFAULT_TZ)
    except Exception:
        return ZoneInfo(DEFAULT_TZ)


def reminder_window(module_code: str) -> timedelta | None:
    """How long before the start the reminder goes out, or None when off."""
    try:
        hours = int(get_config(module_code).get("reminder_hours", 24) or 0)
    except (TypeError, ValueError):
        hours = 24
    return timedelta(hours=hours) if hours > 0 else None


def event_start(event, zone: ZoneInfo) -> datetime:
    """When the event starts, as an aware datetime."""
    from hubra.api.events.services import _event_times

    start, _end = _event_times(event)
    if start is None:
        start = datetime.combine(event.date, ALL_DAY_START)
    return start.replace(tzinfo=zone)


def _aware(value: datetime) -> datetime:
    # SQLite hands back naive datetimes; they are stored as UTC.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _club_url(path: str) -> str:
    from hubra.core.services.email import _get_base_url
    from hubra.core.tenant.context import current_tenant

    base = _get_base_url()
    if not base:
        return ""
    tenant = current_tenant()
    return f"{base}/{tenant.slug}{path}" if tenant else f"{base}{path}"


def _active_members(member_ids):
    from hubra.core.models.member import Member

    if not member_ids:
        return []
    return db.session.scalars(
        select(Member)
        .where(Member.id.in_(member_ids))
        .where(Member.status == "active")
        .where(Member.archived_at.is_(None))
        .order_by(Member.id)
    ).all()


def _mail(member, template: str, **context) -> bool:
    """Queue a reminder mail after commit. False when the member has no
    verified address."""
    from hubra.core.services.email import club_display_name
    from hubra.core.tasks.after_commit import delay_after_commit
    from hubra.core.tasks.email_tasks import send_email_task

    if not member.email or not member.private_email_verified:
        return False
    lang = member.language or DEFAULT_LANG
    ctx = {key: value(lang) if callable(value) else value for key, value in context.items()}
    body_html, body_text, subject = render_mail_template(
        template,
        locale=lang,
        name=member.name,
        club_name=club_display_name(),
        **ctx,
    )
    delay_after_commit(
        send_email_task,
        to_email=member.email,
        to_name=member.name,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
    )
    return True


# ── Events ────────────────────────────────────────────────────────────────────


def event_recipients(event) -> list:
    """Active members who hold a place: a registration that counts, or a
    place an admin gave directly (the attendees list)."""
    from hubra.core.models.event import EventRegistration, event_attendees

    statuses = dict(
        db.session.execute(
            select(EventRegistration.member_id, EventRegistration.status).where(
                EventRegistration.event_id == event.id
            )
        ).all()
    )
    attendees = set(
        db.session.scalars(
            select(event_attendees.c.member_id).where(
                event_attendees.c.event_id == event.id
            )
        ).all()
    )
    ids = {mid for mid, status in statuses.items() if status in _ATTENDING}
    ids |= {mid for mid in attendees if mid not in statuses}
    return _active_members(ids)


@celery_app.task(
    name="hubra.core.tasks.reminder_tasks.send_event_reminders_task",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def send_event_reminders_task(self) -> dict:
    """Event reminders in every club with events on."""
    return _send_event_reminders()


@per_tenant_job("events")
def _send_event_reminders(now: datetime | None = None) -> dict:
    from hubra.api.events.services import event_link
    from hubra.api.notifications.services import notify_member
    from hubra.core.models.event import ClubEvent

    summary = {"events": 0, "notified": 0, "mailed": 0}
    window = reminder_window("events")
    if window is None:
        return summary
    now = now or datetime.now(timezone.utc)
    zone = club_zone()
    local_today = now.astimezone(zone).date()

    candidates = db.session.scalars(
        select(ClubEvent)
        .where(ClubEvent.reminder_sent_at.is_(None))
        .where(ClubEvent.date >= local_today)
        .where(ClubEvent.date <= local_today + window + timedelta(days=1))
        .order_by(ClubEvent.date, ClubEvent.id)
    ).all()
    for event in candidates:
        start = event_start(event, zone)
        due = start - window
        if not (due <= now < start):
            continue
        event.reminder_sent_at = now
        if _aware(event.created_at) > due:
            continue
        summary["events"] += 1
        local = start.astimezone(zone)
        when = lambda lang, local=local, event=event: (  # noqa: E731
            f"{mail_date(local.date(), lang)}, {event.time}"
            if event.time and not event.all_day
            else mail_date(local.date(), lang)
        )
        path = event_link(event.id)
        link = _club_url(path)
        for member in event_recipients(event):
            notify_member(member.id, "info", "Event reminder", event.title, link=path)
            summary["notified"] += 1
            if member.event_reminder_mail and _mail(
                member,
                "event_reminder",
                event_title=event.title,
                when=when,
                location=event.location or "",
                portal_url=link,
            ):
                summary["mailed"] += 1
        emit(EVENT_REMINDER, event_id=event.id)
    return summary


# ── Polls ─────────────────────────────────────────────────────────────────────


def poll_recipients(poll) -> list:
    """Active members who still have a vote to cast: those the poll asks
    (its groups and functions), or every member when it names none; not
    those who voted or gave their vote to a proxy."""
    from hubra.api.polls.services import PollService
    from hubra.core.models.member import Member
    from hubra.core.models.poll import PollProxy, PollVote

    if poll.required_group_ids or poll.required_function_ids:
        ids = set(PollService.get_required_members(poll))
    else:
        ids = set(
            db.session.scalars(
                select(Member.id)
                .where(Member.status == "active")
                .where(Member.archived_at.is_(None))
            ).all()
        )
    ids -= set(
        db.session.scalars(
            select(PollVote.member_id).where(PollVote.poll_id == poll.id)
        ).all()
    )
    ids -= set(
        db.session.scalars(
            select(PollProxy.grantor_id).where(PollProxy.poll_id == poll.id)
        ).all()
    )
    return _active_members(ids)


@celery_app.task(
    name="hubra.core.tasks.reminder_tasks.send_poll_reminders_task",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def send_poll_reminders_task(self) -> dict:
    """Poll reminders in every club with polls on."""
    return _send_poll_reminders()


@per_tenant_job("polls")
def _send_poll_reminders(now: datetime | None = None) -> dict:
    from hubra.api.notifications.services import notify_member
    from hubra.api.polls.services import poll_link
    from hubra.core.models.poll import Poll

    summary = {"polls": 0, "notified": 0, "mailed": 0}
    window = reminder_window("polls")
    if window is None:
        return summary
    now = now or datetime.now(timezone.utc)
    zone = club_zone()

    candidates = db.session.scalars(
        select(Poll)
        .where(Poll.status == "open")
        .where(Poll.reminder_sent_at.is_(None))
        .where(Poll.closes_at.is_not(None))
        .where(Poll.closes_at > now)
        .where(Poll.closes_at <= now + window)
        .order_by(Poll.closes_at, Poll.id)
    ).all()
    for poll in candidates:
        closes = _aware(poll.closes_at)
        due = closes - window
        poll.reminder_sent_at = now
        if _aware(poll.created_at) > due:
            continue
        summary["polls"] += 1
        local = closes.astimezone(zone)
        when = lambda lang, local=local: (  # noqa: E731
            f"{mail_date(local.date(), lang)}, {local:%H:%M}"
        )
        path = poll_link(poll.id)
        link = _club_url(path)
        for member in poll_recipients(poll):
            notify_member(
                member.id,
                "warning",
                f"Reminder: {poll.question}",
                "Please cast your vote before the poll closes.",
                link=path,
            )
            summary["notified"] += 1
            if member.poll_reminder_mail and _mail(
                member,
                "poll_reminder",
                question=poll.question,
                when=when,
                portal_url=link,
            ):
                summary["mailed"] += 1
        emit(POLL_CLOSING, poll_id=poll.id)
    return summary
