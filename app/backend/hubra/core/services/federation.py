"""Federation view: an umbrella association and its member clubs.

The association (a club with the ``federation`` module on) invites a club by
its address. The club's admins accept or decline in their own settings and
choose whether the association sees who holds the club's functions. Once
linked, the association sees each club's number of active members (and the
contacts, when shared), and member clubs see the events the association
shares with them (``club_events.federation_shared``).

Reads in another club run in that club's schema (``in_club``) and select
plain columns only: ids repeat across club schemas, so loading ORM objects
there would mix them up in the session.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import func, or_, select

from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.event import ClubEvent
from hubra.core.models.federation import FederationLink
from hubra.core.models.function import Function, FunctionHolder
from hubra.core.models.member import Member
from hubra.core.models.tenant import Tenant
from hubra.core.models.user import User
from hubra.core.tenant.club_settings import club_logo_version
from hubra.core.tenant.context import in_club

MAX_CLUBS = 500
MAX_SHARED_EVENTS = 30
MAX_CONTACTS = 30


def _club(tenant_id: int) -> Tenant | None:
    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None or tenant.deleted_at is not None or tenant.status != "active":
        return None
    return tenant


def _club_head(tenant: Tenant) -> dict:
    return {
        "slug": tenant.slug,
        "name": tenant.name,
        "logoVersion": club_logo_version(tenant),
    }


# ── The association's side ────────────────────────────────────────────────────


def invite(federation: Tenant, slug: str, by: str) -> FederationLink:
    slug = (slug or "").strip().lower().strip("/")
    if not slug:
        raise_error(400, "VALIDATION_ERROR", "Give the club's address")
    club = db.session.scalar(select(Tenant).where(Tenant.slug == slug))
    if club is None or _club(club.id) is None:
        raise_error(404, "NOT_FOUND", "There is no club at this address")
    if club.id == federation.id:
        raise_error(400, "VALIDATION_ERROR", "An association can't invite itself")
    links = db.session.scalars(
        select(FederationLink).where(FederationLink.federation_id == federation.id)
    ).all()
    if any(link.club_id == club.id for link in links):
        raise_error(409, "ALREADY_LINKED", "This club is already invited or a member")
    if len(links) >= MAX_CLUBS:
        raise_error(400, "TOO_MANY_CLUBS", f"At most {MAX_CLUBS} member clubs")
    link = FederationLink(
        federation_id=federation.id,
        club_id=club.id,
        status="invited",
        invited_by=(by or "")[:255],
    )
    db.session.add(link)
    db.session.commit()
    return link


def link_of_federation(federation: Tenant, link_id: int) -> FederationLink:
    link = db.session.get(FederationLink, link_id)
    if link is None or link.federation_id != federation.id:
        raise_error(404, "NOT_FOUND", "No such member club")
    return link


def remove(link: FederationLink) -> None:
    db.session.delete(link)
    db.session.commit()


def _active_members() -> int:
    return (
        db.session.scalar(
            select(func.count(Member.id)).where(
                Member.status == "active",
                Member.archived_at.is_(None),
                Member.deleted_at.is_(None),
            )
        )
        or 0
    )


def _contacts() -> list[dict]:
    """Who holds the club's functions, with an address meant for the club.

    The function's own mail address comes first, then the holder's club
    address; a holder's private sign-in address is never shown.
    """
    rows = db.session.execute(
        select(
            Function.name,
            Function.mailbox_ref,
            User.first_name,
            User.last_name,
            Member.public_email,
        )
        .join(FunctionHolder, FunctionHolder.function_id == Function.id)
        .join(Member, Member.id == FunctionHolder.member_id)
        .join(User, User.id == Member.user_id)
        .where(Member.archived_at.is_(None), Member.deleted_at.is_(None))
        .order_by(Function.name, User.last_name, User.first_name)
        .limit(MAX_CONTACTS)
    ).all()
    return [
        {
            "function": name,
            "name": f"{first or ''} {last or ''}".strip(),
            "email": mailbox if mailbox and "@" in mailbox else (public_email or None),
        }
        for name, mailbox, first, last, public_email in rows
    ]


def member_clubs(federation: Tenant) -> list[dict]:
    """The association's member clubs and invitations, with their numbers."""
    from hubra.core.modules import is_enabled

    links = db.session.scalars(
        select(FederationLink)
        .where(FederationLink.federation_id == federation.id)
        .order_by(FederationLink.created_at)
    ).all()
    out = []
    for link in links:
        club = _club(link.club_id)
        if club is None:
            continue
        row = {
            "id": link.id,
            "status": link.status,
            "shareContacts": link.share_contacts,
            "invitedAt": link.created_at.isoformat(),
            "acceptedAt": link.accepted_at.isoformat() if link.accepted_at else None,
            **_club_head(club),
            "members": None,
            "contacts": [],
        }
        # An invited club shares nothing until it accepts.
        if link.status == "active":
            with in_club(club):
                row["members"] = _active_members()
                if link.share_contacts and is_enabled("functions", club.id):
                    row["contacts"] = _contacts()
        out.append(row)
    out.sort(key=lambda r: (r["status"] != "active", r["name"].lower()))
    return out


# ── The member club's side ────────────────────────────────────────────────────


def associations(club: Tenant) -> list[dict]:
    """The associations a club belongs to or is invited by."""
    links = db.session.scalars(
        select(FederationLink)
        .where(FederationLink.club_id == club.id)
        .order_by(FederationLink.created_at)
    ).all()
    out = []
    for link in links:
        federation = _club(link.federation_id)
        if federation is None:
            continue
        out.append(
            {
                "id": link.id,
                "status": link.status,
                "shareContacts": link.share_contacts,
                "invitedBy": link.invited_by or None,
                "invitedAt": link.created_at.isoformat(),
                "acceptedAt": link.accepted_at.isoformat()
                if link.accepted_at
                else None,
                **_club_head(federation),
            }
        )
    return out


def link_of_club(club: Tenant, link_id: int) -> FederationLink:
    link = db.session.get(FederationLink, link_id)
    if link is None or link.club_id != club.id:
        raise_error(404, "NOT_FOUND", "No such association")
    return link


def accept(link: FederationLink, share_contacts: bool) -> FederationLink:
    if link.status != "active":
        link.status = "active"
        link.accepted_at = datetime.now(timezone.utc)
    link.share_contacts = bool(share_contacts)
    db.session.commit()
    return link


def set_share_contacts(link: FederationLink, share_contacts: bool) -> FederationLink:
    if link.status != "active":
        raise_error(409, "NOT_ACCEPTED", "Accept the invitation first")
    link.share_contacts = bool(share_contacts)
    db.session.commit()
    return link


def _shared_events(today: date) -> list[dict]:
    rows = db.session.execute(
        select(
            ClubEvent.id,
            ClubEvent.title,
            ClubEvent.date,
            ClubEvent.end_date,
            ClubEvent.time,
            ClubEvent.all_day,
            ClubEvent.location,
            ClubEvent.description,
            ClubEvent.meeting_url,
            ClubEvent.type,
        )
        .where(
            ClubEvent.federation_shared.is_(True),
            or_(
                ClubEvent.date >= today,
                ClubEvent.end_date >= today,
            ),
        )
        .order_by(ClubEvent.date, ClubEvent.id)
        .limit(MAX_SHARED_EVENTS)
    ).all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "date": r.date.isoformat(),
            "endDate": r.end_date.isoformat() if r.end_date else None,
            "time": None if r.all_day else r.time,
            "allDay": bool(r.all_day),
            "location": r.location,
            "description": r.description,
            "onlineUrl": r.meeting_url,
            "type": r.type,
        }
        for r in rows
    ]


def shared_events(club: Tenant, today: date | None = None) -> list[dict]:
    """Upcoming events the club's associations share with their members."""
    from hubra.core.modules import is_enabled

    today = today or date.today()
    links = db.session.scalars(
        select(FederationLink).where(
            FederationLink.club_id == club.id, FederationLink.status == "active"
        )
    ).all()
    out: list[dict] = []
    for link in links:
        federation = _club(link.federation_id)
        if federation is None:
            continue
        if not (
            is_enabled("federation", federation.id)
            and is_enabled("events", federation.id)
        ):
            continue
        with in_club(federation):
            events = _shared_events(today)
        head = {"federation": federation.name, "federationSlug": federation.slug}
        out.extend({**e, **head} for e in events)
    out.sort(key=lambda e: (e["date"], e["time"] or "", e["title"]))
    return out[:MAX_SHARED_EVENTS]
