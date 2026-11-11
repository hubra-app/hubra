"""One calendar for all of a person's clubs: a personal iCalendar URL with
the events of every club they are a member of, or only those they signed up
for. Calendar apps cannot sign in, so the URL carries a signed token with
the account, a version (renewing it stops older URLs) and the scope."""

from __future__ import annotations

from datetime import date, timedelta

from flask import current_app, url_for
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import select

from hubra.api.events.services import EventsService, ical_document, ical_events
from hubra.core.extensions import db
from hubra.core.models.event import EventRegistration
from hubra.core.models.member import Member
from hubra.core.models.user import User

SCOPES = ("all", "mine")
# Sign-ups that count as "mine".
_SIGNED_UP = ("registered", "approved", "waitlisted", "attended")
# The last 90 days and everything ahead, as the club feeds.
PAST_DAYS = 90


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(current_app.config["SECRET_KEY"], salt="account-calendar")


def feed_url(user: User, scope: str) -> str:
    token = _serializer().dumps(
        {"u": user.id, "v": user.calendar_feed_version or 0, "s": scope}
    )
    return url_for("account_bp.account_calendar_feed", token=token, _external=True)


def feed_urls(user: User) -> dict:
    return {scope: feed_url(user, scope) for scope in SCOPES}


def user_for(token: str) -> tuple[User, str] | None:
    """The account and scope behind a feed token, or None when it is
    forged, renewed since or the account is gone or disabled."""
    try:
        data = _serializer().loads(token)
    except BadSignature:
        return None
    user = db.session.get(User, data.get("u") or 0)
    if user is None or user.is_disabled:
        return None
    if data.get("v", 0) != (user.calendar_feed_version or 0):
        return None
    scope = data.get("s")
    return (user, scope) if scope in SCOPES else None


def build(user: User, scope: str) -> str:
    """The calendar: every club where the person is an active member with
    events on, each event named with its club."""
    from hubra.core.auth.services import AuthService
    from hubra.core.models.tenant import Tenant
    from hubra.core.modules import is_enabled
    from hubra.core.tenant.context import in_club

    since = (date.today() - timedelta(days=PAST_DAYS)).isoformat()
    vevents: list[str] = []
    for club in AuthService.find_user_tenants(user.id):
        if not club.get("member_id") or not club.get("tenant_id"):
            continue
        tenant = db.session.get(Tenant, club["tenant_id"])
        if tenant is None:
            continue
        with in_club(tenant):
            if not is_enabled("events"):
                continue
            member = db.session.get(Member, club["member_id"])
            if member is None or member.archived_at is not None or member.is_blocked:
                continue
            events = EventsService.list(from_str=since)
            if scope == "mine":
                mine = set(
                    db.session.scalars(
                        select(EventRegistration.event_id).where(
                            EventRegistration.member_id == member.id,
                            EventRegistration.status.in_(_SIGNED_UP),
                        )
                    )
                )
                events = [e for e in events if e.id in mine]
            vevents += ical_events(events, tenant.slug, tenant.name)
    return ical_document(vevents, "Hubra")
