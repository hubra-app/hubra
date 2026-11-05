"""The weekly digest: a summary of the club's week by mail or Discord.

A member who turned it on (``members.weekly_digest_mail``, or the Discord
column of the "digest" topic, Account › Notifications) gets it on Monday
morning, club time: the events of the coming seven days (marked where they
signed up), the posts of the past seven days and the open polls they can
still vote in. Nothing to tell, nothing sent. ``members.digest_sent_at``
keeps it to one a week, so the hourly run can catch up when the worker was
down at seven.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from hubra.core.extensions import db
from hubra.core.modules import is_enabled, per_tenant_job
from hubra.core.services.mail_format import mail_date
from hubra.core.tasks import celery_app
from hubra.core.timeutil import as_utc
from hubra.core.tasks.reminder_tasks import (
    _ATTENDING,
    _club_url,
    _mail,
    club_zone,
    poll_recipients,
)

logger = logging.getLogger(__name__)

SEND_WEEKDAY = 0  # Monday
SEND_HOUR = 7  # club time; later runs that day catch up
DAYS = 7
MAX_EVENTS = 10
MAX_POSTS = 5
MAX_POLLS = 5
# Sent less than this long ago: this week's digest went out already.
_GAP = timedelta(days=6)


@celery_app.task(
    name="hubra.core.tasks.digest_tasks.send_weekly_digests_task",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def send_weekly_digests_task(self) -> dict:
    """Weekly digests in every club (members is always on)."""
    return _send_weekly_digests()


def _due(now: datetime) -> bool:
    local = now.astimezone(club_zone())
    return local.weekday() == SEND_WEEKDAY and local.hour >= SEND_HOUR


def _events(today: date) -> list:
    from hubra.core.models.event import ClubEvent

    if not is_enabled("events"):
        return []
    return db.session.scalars(
        select(ClubEvent)
        .where(ClubEvent.date >= today)
        .where(ClubEvent.date < today + timedelta(days=DAYS))
        .order_by(ClubEvent.date, ClubEvent.time, ClubEvent.id)
    ).all()


def _signed_up(event_ids: list[int]) -> dict[int, set[int]]:
    """Per member, the events among *event_ids* they hold a place in."""
    from hubra.core.models.event import EventRegistration, event_attendees

    out: dict[int, set[int]] = {}
    if not event_ids:
        return out
    regs = db.session.execute(
        select(
            EventRegistration.member_id,
            EventRegistration.event_id,
            EventRegistration.status,
        ).where(EventRegistration.event_id.in_(event_ids))
    ).all()
    seen = set()
    for member_id, event_id, status in regs:
        seen.add((member_id, event_id))
        if status in _ATTENDING:
            out.setdefault(member_id, set()).add(event_id)
    for event_id, member_id in db.session.execute(
        select(event_attendees.c.event_id, event_attendees.c.member_id).where(
            event_attendees.c.event_id.in_(event_ids)
        )
    ).all():
        if (member_id, event_id) not in seen:
            out.setdefault(member_id, set()).add(event_id)
    return out


def _posts(since: datetime) -> list:
    from hubra.core.models.post import Post

    if not is_enabled("posts"):
        return []
    return db.session.scalars(
        select(Post)
        .where(Post.created_at >= since)
        .order_by(Post.created_at.desc(), Post.id.desc())
    ).all()


def _open_polls(now: datetime) -> list[tuple]:
    """Open polls with the members who can still vote in each."""
    from hubra.core.models.poll import Poll

    if not is_enabled("polls"):
        return []
    polls = db.session.scalars(
        select(Poll)
        .where(Poll.status == "open")
        .where((Poll.closes_at.is_(None)) | (Poll.closes_at > now))
        .order_by(Poll.closes_at.is_(None), Poll.closes_at, Poll.id)
    ).all()
    return [(poll, {m.id for m in poll_recipients(poll)}) for poll in polls]


def _when(event, lang: str) -> str:
    day = mail_date(event.date, lang)
    return f"{day}, {event.time}" if event.time and not event.all_day else day


def _direct_message(member, events, mine, posts, votes) -> bool:
    """The digest as a Discord direct message (the app channels the member
    turned on for the "digest" topic): one embed with a field per part."""
    from hubra.core.notifications.channels import send_without_bell
    from hubra.core.models.user import User

    user = db.session.get(User, member.user_id) if member.user_id else None
    lang = (user.language if user else None) or "de-CH"
    de = not lang.startswith("en")
    zone = club_zone()

    def line(text: str, path: str) -> str:
        url = _club_url(path)
        return f"[{text}]({url})" if url else text

    fields = []
    if events:
        rows = [
            ("✅ " if e.id in mine else "• ")
            + line(e.title, f"/app/operations/events?event={e.id}")
            + f" · {_when(e, lang)}"
            for e in events
        ]
        fields.append({"name": "Anlässe" if de else "Events", "value": "\n".join(rows)})
    if posts:
        rows = [
            "• " + line(p.title, f"/app/operations/posts/{p.id}")
            for p in posts[:MAX_POSTS]
        ]
        fields.append(
            {"name": "Neue Beiträge" if de else "New posts", "value": "\n".join(rows)}
        )
    if votes:
        rows = []
        for p in votes[:MAX_POLLS]:
            row = "• " + line(p.question, f"/app/operations/polls?poll={p.id}")
            if p.closes_at:
                closes = as_utc(p.closes_at).astimezone(zone).date()
                row += f" · {'bis' if de else 'until'} {mail_date(closes, lang)}"
            rows.append(row)
        fields.append(
            {
                "name": "Noch abstimmen" if de else "Still to vote",
                "value": "\n".join(rows),
            }
        )
    for field in fields:
        field["value"] = field["value"][:1024]
    send_without_bell(
        member.id,
        "info",
        "Your week",
        "",
        link="/app/dashboard",
        topic="digest",
        extra={"fields": fields},
    )
    return True


@per_tenant_job("members")
def _send_weekly_digests(now: datetime | None = None) -> dict:
    from hubra.core.models.member import Member

    summary = {"members": 0, "mailed": 0, "empty": 0}
    now = now or datetime.now(timezone.utc)
    if not _due(now):
        return summary
    from hubra.core.notifications.channels import wants_any_app

    candidates = db.session.scalars(
        select(Member)
        .where(Member.status == "active")
        .where(Member.archived_at.is_(None))
        .where((Member.digest_sent_at.is_(None)) | (Member.digest_sent_at < now - _GAP))
        .order_by(Member.id)
    ).all()
    members = [
        m
        for m in candidates
        if m.weekly_digest_mail or wants_any_app(m.notify_prefs, "digest")
    ]
    if not members:
        return summary

    zone = club_zone()
    today = now.astimezone(zone).date()
    events = _events(today)
    signed_up = _signed_up([e.id for e in events])
    posts = _posts(now - timedelta(days=DAYS))
    polls = _open_polls(now)

    for member in members:
        summary["members"] += 1
        member.digest_sent_at = now
        mine = signed_up.get(member.id, set())
        votes = [poll for poll, voters in polls if member.id in voters]
        if not (events or posts or votes):
            summary["empty"] += 1
            continue

        def event_rows(lang, events=events, mine=mine):
            return [
                {
                    "title": e.title,
                    "when": _when(e, lang),
                    "location": e.location,
                    "signed_up": e.id in mine,
                    "url": _club_url(f"/app/operations/events?event={e.id}"),
                }
                for e in events[:MAX_EVENTS]
            ]

        def poll_rows(lang, votes=votes):
            return [
                {
                    "question": p.question,
                    "closes": (
                        mail_date(as_utc(p.closes_at).astimezone(zone).date(), lang)
                        if p.closes_at
                        else None
                    ),
                    "url": _club_url(f"/app/operations/polls?poll={p.id}"),
                }
                for p in votes[:MAX_POLLS]
            ]

        if wants_any_app(member.notify_prefs, "digest"):
            if _direct_message(member, events[:MAX_EVENTS], mine, posts, votes):
                summary["messaged"] = summary.get("messaged", 0) + 1
        if not member.weekly_digest_mail:
            continue
        if _mail(
            member,
            "weekly_digest",
            events=event_rows,
            more_events=max(len(events) - MAX_EVENTS, 0),
            posts=[
                {
                    "title": p.title,
                    "summary": p.summary,
                    "url": _club_url(f"/app/operations/posts/{p.id}"),
                }
                for p in posts[:MAX_POSTS]
            ],
            more_posts=max(len(posts) - MAX_POSTS, 0),
            polls=poll_rows,
            more_polls=max(len(votes) - MAX_POLLS, 0),
            portal_url=_club_url("/app"),
        ):
            summary["mailed"] += 1
    db.session.commit()
    logger.info("weekly_digest %s", summary)
    return summary
