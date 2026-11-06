"""Support cases: problem reports and feature requests (see
``core/models/support_case.py``).

Who sees what:
  * the reporter, and people staff added to a case (``support_case_people``):
    those cases and the comments that are not internal;
  * everyone signed in: the public roadmap (feature requests staff put on
    it), with votes; anyone, signed in or not: the same list without votes
    of their own (``/api/v1/roadmap``);
  * platform staff with ``support.cases``: everything, in manage › Support.

New cases go to platform admins as an alert (type ``support_cases``: mail,
and the platform Discord log when it is set up).  The reporter gets a mail
when staff answer or change the status.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from sqlalchemy import func, or_, select

from hubra.core.extensions import db
from hubra.core.models.support_case import (
    RoadmapVote,
    SupportCase,
    SupportCaseComment,
    SupportCasePerson,
    SupportCaseVote,
)
from hubra.core.models.tenant import Tenant
from hubra.core.models.user import User

logger = logging.getLogger(__name__)

# question: the contact form on the support site (support.hubra.club).
KINDS = ("bug", "feature", "question")
STATUSES = ("open", "planned", "in_progress", "done", "closed")
# Done or closed: nothing more happens.
FINISHED = frozenset({"done", "closed"})
SEVERITIES = ("minor", "annoying", "blocking")
AREAS = (
    "members",
    "finance",
    "events",
    "posts",
    "polls",
    "groups",
    "inventory",
    "mail",
    "settings",
    "account",
    # A module the club would like (Settings › Module › "Fehlt ein Modul?").
    "modules",
    "other",
)
AREA_LABELS = {
    "members": {"de": "Mitglieder", "en": "Members"},
    "finance": {"de": "Finanzen", "en": "Finance"},
    "events": {"de": "Anlässe", "en": "Events"},
    "posts": {"de": "Beiträge", "en": "Posts"},
    "polls": {"de": "Umfragen", "en": "Polls"},
    "groups": {"de": "Gruppen", "en": "Groups"},
    "inventory": {"de": "Inventar", "en": "Inventory"},
    "mail": {"de": "Mail", "en": "Mail"},
    "settings": {"de": "Einstellungen", "en": "Settings"},
    "account": {"de": "Konto", "en": "Account"},
    "modules": {"de": "Modul", "en": "Module"},
    "other": {"de": "Anderes", "en": "Other"},
}
# Statuses the public roadmap shows (a closed idea drops off).
ROADMAP_STATUSES = ("open", "planned", "in_progress", "done")
# Where an idea shows on the one roadmap (the planned roadmap's statuses,
# plus "idea": proposed, not planned yet).
IDEA_TO_ROADMAP = {
    "open": "idea",
    "planned": "later",
    "in_progress": "now",
    "done": "done",
}
# What people can still vote for: not what is being built or shipped.
VOTEABLE = frozenset({"idea", "later", "next"})

TITLE_MAX = 200
TEXT_MAX = 5000
COMMENT_MAX = 5000

# What the app may send about the device, and nothing else.
_FP_TEXT = {
    "browser": 40,
    "browserVersion": 20,
    "os": 40,
    "osVersion": 20,
    "deviceType": 10,
    "language": 20,
    "theme": 10,
}
_FP_INT = ("screenWidth", "screenHeight", "viewportWidth", "viewportHeight")
_DEVICE_TYPES = ("phone", "tablet", "desktop")


class SupportError(ValueError):
    pass


def clean_fingerprint(raw) -> dict:
    """Keep the known device fields only, trimmed to sane sizes."""
    if not isinstance(raw, dict):
        return {}
    out: dict = {}
    for key, limit in _FP_TEXT.items():
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            out[key] = value.strip()[:limit]
    for key in _FP_INT:
        value = raw.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if 0 < value <= 20000:
                out[key] = int(value)
    if out.get("deviceType") not in _DEVICE_TYPES:
        out.pop("deviceType", None)
    if out.get("theme") not in ("light", "dark"):
        out.pop("theme", None)
    return out


def _with_version(fp: dict) -> dict:
    """The server's own version, not what the browser claims."""
    try:
        from hubra.core.services.version import VersionService

        fp["appVersion"] = str(VersionService.get_version())[:40]
    except Exception:  # noqa: BLE001
        fp.pop("appVersion", None)
    return fp


def _text(value, field: str, limit: int, *, required: bool = False) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise SupportError(f"{field} is required")
        return None
    if not isinstance(value, str):
        raise SupportError(f"{field} must be text")
    value = value.strip()
    if len(value) > limit:
        raise SupportError(f"{field} is too long (at most {limit} characters)")
    return value


def _page(value) -> str | None:
    """The app path the report came from, without query or fragment."""
    if not isinstance(value, str) or not value.startswith("/"):
        return None
    return value.split("?", 1)[0].split("#", 1)[0][:300]


def submit(user_id: int, tenant_id: int | None, body: dict) -> SupportCase:
    kind = body.get("kind")
    if kind not in KINDS:
        raise SupportError("kind must be bug, feature or question")
    title = _text(body.get("title"), "title", TITLE_MAX, required=True)
    description = _text(body.get("description"), "description", TEXT_MAX, required=True)
    details: dict = {}
    keys = {"bug": ("steps", "expected"), "feature": ("useCase",)}.get(kind, ())
    for key in keys:
        value = _text(body.get(key), key, TEXT_MAX)
        if value:
            details[key] = value
    area = body.get("area")
    if area is not None and area not in AREAS:
        raise SupportError("Unknown area")
    severity = body.get("severity") if kind == "bug" else None
    if severity is not None and severity not in SEVERITIES:
        raise SupportError("Unknown severity")

    case = SupportCase(
        kind=kind,
        status="open",
        title=title,
        description=description,
        details=details or None,
        area=area,
        severity=severity,
        page=_page(body.get("page")),
        fingerprint=_with_version(clean_fingerprint(body.get("fingerprint"))) or None,
        user_id=user_id,
        tenant_id=tenant_id,
    )
    db.session.add(case)
    db.session.flush()
    if kind == "feature":
        # Whoever asks for it wants it: their vote counts once it is public.
        db.session.add(SupportCaseVote(case_id=case.id, user_id=user_id))
    return case


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
GUEST_KINDS = ("bug", "question")
GUEST_REASONS = ("wrong_recipient", "unwanted_mail", "other")


def submit_guest(body: dict) -> SupportCase:
    """A report from someone without an account (or not signed in): a mail
    that reached the wrong person, mails they don't want, or another
    problem.  They leave an address so staff can answer; no vote, no club,
    and nothing is mailed to that address until staff answers."""
    kind = body.get("kind") or "bug"
    if kind not in GUEST_KINDS:
        raise SupportError("kind must be bug or question")
    email = _text(body.get("email"), "email", 254, required=True)
    if not _EMAIL_RE.match(email or ""):
        raise SupportError("email is not a valid address")
    name = _text(body.get("name"), "name", 120)
    reason = body.get("reason") or "other"
    if reason not in GUEST_REASONS:
        raise SupportError("Unknown reason")
    title = _text(body.get("title"), "title", TITLE_MAX, required=True)
    description = _text(body.get("description"), "description", TEXT_MAX, required=True)
    details: dict = {"guest": {"email": email.lower(), "name": name, "reason": reason}}
    mail = _text(body.get("mail"), "mail", 120)
    if mail:
        details["guest"]["mail"] = mail
    case = SupportCase(
        kind=kind,
        status="open",
        title=title,
        description=description,
        details=details,
        area="mail" if reason != "other" else None,
        severity="annoying" if kind == "bug" else None,
        page=_page(body.get("page")),
        fingerprint=_with_version(clean_fingerprint(body.get("fingerprint"))) or None,
        user_id=None,
        tenant_id=None,
    )
    db.session.add(case)
    db.session.flush()
    return case


def guest_contact(case: SupportCase) -> dict | None:
    """The address a guest report left, or None for an account's case."""
    if case.user_id is not None:
        return None
    guest = (case.details or {}).get("guest")
    return guest if isinstance(guest, dict) and guest.get("email") else None


def _reporter(case: SupportCase, user: User | None) -> dict | None:
    if user is not None:
        return _person(user)
    guest = guest_contact(case)
    if guest is None:
        return None
    return {
        "id": None,
        "name": guest.get("name") or guest["email"],
        "email": guest["email"],
        "guest": True,
        "reason": guest.get("reason"),
        "mail": guest.get("mail"),
    }


# ── Reading ───────────────────────────────────────────────────────────────────


def _votes(case_ids: list[int]) -> dict[int, int]:
    if not case_ids:
        return {}
    rows = db.session.execute(
        select(SupportCaseVote.case_id, func.count())
        .where(SupportCaseVote.case_id.in_(case_ids))
        .group_by(SupportCaseVote.case_id)
    ).all()
    return dict(rows)


def _comment_counts(case_ids: list[int], *, staff: bool) -> dict[int, int]:
    if not case_ids:
        return {}
    stmt = select(SupportCaseComment.case_id, func.count()).where(
        SupportCaseComment.case_id.in_(case_ids)
    )
    if not staff:
        stmt = stmt.where(SupportCaseComment.internal.is_(False))
    rows = db.session.execute(stmt.group_by(SupportCaseComment.case_id)).all()
    return dict(rows)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _person(user: User | None) -> dict | None:
    if user is None:
        return None
    return {"id": user.id, "name": user.name, "email": user.email}


def _merged_into(case: SupportCase) -> dict | None:
    if case.merged_into_id is None:
        return None
    target = db.session.get(SupportCase, case.merged_into_id)
    if target is None:
        return None
    return {"id": target.id, "title": target.title, "status": target.status}


def as_dict(case: SupportCase, *, votes: int = 0, comments: int = 0) -> dict:
    """What the reporter sees of their case."""
    details = case.details or {}
    return {
        "id": case.id,
        "kind": case.kind,
        "status": case.status,
        "title": case.title,
        "description": case.description,
        "steps": details.get("steps"),
        "expected": details.get("expected"),
        "useCase": details.get("useCase"),
        "area": case.area,
        "severity": case.severity,
        "page": case.page,
        "fingerprint": case.fingerprint or {},
        "isPublic": case.is_public,
        "roadmapItem": case.roadmap_item,
        "mergedInto": _merged_into(case),
        "votes": votes,
        "commentCount": comments,
        "createdAt": _iso(case.created_at),
        "updatedAt": _iso(case.updated_at),
        "closedAt": _iso(case.closed_at),
    }


def comment_dict(
    c: SupportCaseComment, author: User | None, *, staff_view: bool
) -> dict:
    out = {
        "id": c.id,
        "body": c.body,
        "fromStaff": c.from_staff,
        "internal": c.internal,
        "createdAt": _iso(c.created_at),
        # The reporter sees "Hubra team" for staff, not who it was.
        "author": (
            author.name
            if author is not None and (staff_view or not c.from_staff)
            else None
        ),
    }
    return out


def comments_for(case: SupportCase, *, staff: bool) -> list[dict]:
    stmt = (
        select(SupportCaseComment, User)
        .outerjoin(User, User.id == SupportCaseComment.user_id)
        .where(SupportCaseComment.case_id == case.id)
    )
    if not staff:
        stmt = stmt.where(SupportCaseComment.internal.is_(False))
    rows = db.session.execute(
        stmt.order_by(SupportCaseComment.created_at, SupportCaseComment.id)
    ).all()
    return [comment_dict(c, u, staff_view=staff) for c, u in rows]


def _added_to(user_id: int):
    return select(SupportCasePerson.case_id).where(
        SupportCasePerson.user_id == user_id
    )


def mine(user_id: int) -> list[dict]:
    """The person's cases: sent by them, or staff added them."""
    cases = db.session.scalars(
        select(SupportCase)
        .where(
            or_(SupportCase.user_id == user_id, SupportCase.id.in_(_added_to(user_id)))
        )
        .order_by(SupportCase.created_at.desc(), SupportCase.id.desc())
    ).all()
    ids = [c.id for c in cases]
    votes = _votes(ids)
    counts = _comment_counts(ids, staff=False)
    return [
        as_dict(c, votes=votes.get(c.id, 0), comments=counts.get(c.id, 0))
        for c in cases
    ]


def own_case(user_id: int, case_id: int) -> SupportCase | None:
    case = db.session.get(SupportCase, case_id)
    if case is None:
        return None
    if case.user_id != user_id and not db.session.scalar(
        _added_to(user_id).where(SupportCasePerson.case_id == case_id)
    ):
        return None
    return case


def _plan() -> list[dict]:
    from hubra.core.services.version import VersionService

    return VersionService.get_roadmap()


def roadmap(user_id: int | None = None) -> dict:
    """The one public roadmap: the planned items (ROADMAP.yaml) and the ideas
    staff put on it, with votes.

    An idea linked to a planned item (``roadmap_item``) shows as that item,
    and its voters count for it.  Each item is ``{id, source, status, area,
    title, summary, version, link, votes, voteable}`` plus ``voted`` when
    *user_id* is given; ``source`` is ``plan`` or ``idea`` (then ``caseId``).
    ``status`` is now | next | later | done | idea.
    """
    plan = _plan()
    plan_ids = {p["id"] for p in plan}

    cases = db.session.scalars(
        select(SupportCase)
        .where(SupportCase.kind == "feature")
        .where(SupportCase.merged_into_id.is_(None))
        .where(
            or_(
                SupportCase.roadmap_item.in_(plan_ids or {""}),
                (SupportCase.is_public.is_(True))
                & SupportCase.status.in_(ROADMAP_STATUSES),
            )
        )
    ).all()
    linked: dict[str, list[int]] = {}
    ideas: list[SupportCase] = []
    for c in cases:
        if c.roadmap_item in plan_ids:
            linked.setdefault(c.roadmap_item, []).append(c.id)
        elif c.is_public:
            ideas.append(c)

    case_ids = [c.id for c in cases]
    case_voters: dict[int, set[int]] = {}
    if case_ids:
        for cid, uid in db.session.execute(
            select(SupportCaseVote.case_id, SupportCaseVote.user_id).where(
                SupportCaseVote.case_id.in_(case_ids)
            )
        ).all():
            case_voters.setdefault(cid, set()).add(uid)
    item_voters: dict[str, set[int]] = {}
    if plan_ids:
        for item, uid in db.session.execute(
            select(RoadmapVote.item, RoadmapVote.user_id).where(
                RoadmapVote.item.in_(plan_ids)
            )
        ).all():
            item_voters.setdefault(item, set()).add(uid)

    def finish(entry: dict, voters: set[int]) -> dict:
        entry["votes"] = len(voters)
        entry["voteable"] = entry["status"] in VOTEABLE
        if user_id is not None:
            entry["voted"] = user_id in voters
        return entry

    items: list[dict] = []
    for p in plan:
        voters = set(item_voters.get(p["id"], set()))
        for cid in linked.get(p["id"], []):
            voters |= case_voters.get(cid, set())
        items.append(
            finish({**p, "source": "plan", "ideas": len(linked.get(p["id"], []))}, voters)
        )
    idea_items = []
    for c in ideas:
        idea_items.append(
            finish(
                {
                    "id": f"idea-{c.id}",
                    "caseId": c.id,
                    "source": "idea",
                    "status": IDEA_TO_ROADMAP[c.status],
                    "area": AREA_LABELS.get(c.area or "", {}),
                    # Ideas are written in one language; the apps show it as is.
                    "title": {"de": c.title, "en": c.title},
                    "summary": {"de": c.description, "en": c.description},
                    "version": None,
                    "link": None,
                    "createdAt": _iso(c.created_at),
                },
                case_voters.get(c.id, set()),
            )
        )
    idea_items.sort(key=lambda i: (-i["votes"], i["caseId"]))
    items.extend(idea_items)
    return {"statuses": ["now", "next", "later", "done", "idea"], "items": items}


def vote(user_id: int, case_id: int, on: bool) -> int:
    case = db.session.get(SupportCase, case_id)
    if (
        case is None
        or case.kind != "feature"
        or not case.is_public
        or case.merged_into_id is not None
        or case.status not in ROADMAP_STATUSES
    ):
        raise LookupError("Not on the roadmap")
    if case.roadmap_item and case.roadmap_item in {p["id"] for p in _plan()}:
        # It shows as the planned item now: the vote goes there.
        return vote_item(user_id, case.roadmap_item, on)
    if IDEA_TO_ROADMAP[case.status] not in VOTEABLE:
        raise SupportError("Voting is closed for this idea")
    existing = db.session.scalar(
        select(SupportCaseVote)
        .where(SupportCaseVote.case_id == case_id)
        .where(SupportCaseVote.user_id == user_id)
    )
    if on and existing is None:
        db.session.add(SupportCaseVote(case_id=case_id, user_id=user_id))
    elif not on and existing is not None:
        db.session.delete(existing)
    db.session.flush()
    return _votes([case_id]).get(case_id, 0)


def vote_item(user_id: int, item_id: str, on: bool) -> int:
    """Vote for a planned item; returns its vote count (distinct people)."""
    item = next((p for p in _plan() if p["id"] == item_id), None)
    if item is None:
        raise LookupError("Not on the roadmap")
    if item["status"] not in VOTEABLE:
        raise SupportError("Voting is closed for this item")
    linked = list(
        db.session.scalars(
            select(SupportCase.id)
            .where(SupportCase.roadmap_item == item_id)
            .where(SupportCase.merged_into_id.is_(None))
        ).all()
    )
    own = db.session.scalar(
        select(RoadmapVote)
        .where(RoadmapVote.item == item_id)
        .where(RoadmapVote.user_id == user_id)
    )
    if on:
        already = own is not None or (
            linked
            and db.session.scalar(
                select(func.count())
                .select_from(SupportCaseVote)
                .where(SupportCaseVote.case_id.in_(linked))
                .where(SupportCaseVote.user_id == user_id)
            )
        )
        if not already:
            db.session.add(RoadmapVote(item=item_id, user_id=user_id))
    else:
        if own is not None:
            db.session.delete(own)
        if linked:
            for v in db.session.scalars(
                select(SupportCaseVote)
                .where(SupportCaseVote.case_id.in_(linked))
                .where(SupportCaseVote.user_id == user_id)
            ).all():
                db.session.delete(v)
    db.session.flush()
    voters = set(
        db.session.scalars(
            select(RoadmapVote.user_id).where(RoadmapVote.item == item_id)
        ).all()
    )
    if linked:
        voters |= set(
            db.session.scalars(
                select(SupportCaseVote.user_id).where(
                    SupportCaseVote.case_id.in_(linked)
                )
            ).all()
        )
    return len(voters)


# ── Staff ─────────────────────────────────────────────────────────────────────


def staff_listing(
    *,
    kind: str | None = None,
    status: str | None = None,
    area: str | None = None,
    query: str | None = None,
    page: int = 1,
    per_page: int = 25,
) -> dict:
    """``status``: one of STATUSES, ``active`` (not done or closed) or None (all)."""
    stmt = select(SupportCase)
    if kind:
        stmt = stmt.where(SupportCase.kind == kind)
    if area:
        stmt = stmt.where(SupportCase.area == area)
    if status == "active":
        stmt = stmt.where(SupportCase.status.not_in(FINISHED))
    elif status:
        stmt = stmt.where(SupportCase.status == status)
    if query:
        like = f"%{query.lower()}%"
        conditions = [
            func.lower(SupportCase.title).like(like),
            func.lower(SupportCase.description).like(like),
        ]
        if query.lstrip("#").isdigit():
            conditions.append(SupportCase.id == int(query.lstrip("#")))
        stmt = stmt.where(or_(*conditions))
    total = db.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    cases = db.session.scalars(
        stmt.order_by(SupportCase.updated_at.desc(), SupportCase.id.desc())
        .limit(per_page)
        .offset((page - 1) * per_page)
    ).all()

    ids = [c.id for c in cases]
    votes = _votes(ids)
    counts = _comment_counts(ids, staff=True)
    users = _users({c.user_id for c in cases})
    clubs = _clubs({c.tenant_id for c in cases})
    waiting = _waiting_on_staff(ids)
    items = []
    for c in cases:
        item = as_dict(c, votes=votes.get(c.id, 0), comments=counts.get(c.id, 0))
        item["reporter"] = _reporter(c, users.get(c.user_id))
        item["club"] = clubs.get(c.tenant_id)
        item["awaitingReply"] = c.id in waiting and c.status not in FINISHED
        items.append(item)

    open_counts = dict(
        db.session.execute(
            select(SupportCase.kind, func.count())
            .where(SupportCase.status.not_in(FINISHED))
            .group_by(SupportCase.kind)
        ).all()
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "perPage": per_page,
        "openCounts": {k: open_counts.get(k, 0) for k in KINDS},
    }


def _users(ids: set) -> dict[int, User]:
    ids = {i for i in ids if i is not None}
    if not ids:
        return {}
    return {u.id: u for u in db.session.scalars(select(User).where(User.id.in_(ids)))}


def _clubs(ids: set) -> dict[int, dict]:
    ids = {i for i in ids if i is not None}
    if not ids:
        return {}
    rows = db.session.execute(
        select(Tenant.id, Tenant.name, Tenant.slug).where(Tenant.id.in_(ids))
    ).all()
    return {tid: {"id": tid, "name": name, "slug": slug} for tid, name, slug in rows}


def _waiting_on_staff(case_ids: list[int]) -> set[int]:
    """Cases whose last visible comment is the reporter's."""
    if not case_ids:
        return set()
    last = (
        select(
            SupportCaseComment.case_id,
            func.max(SupportCaseComment.id).label("last_id"),
        )
        .where(SupportCaseComment.case_id.in_(case_ids))
        .where(SupportCaseComment.internal.is_(False))
        .group_by(SupportCaseComment.case_id)
        .subquery()
    )
    rows = db.session.execute(
        select(SupportCaseComment.case_id)
        .join(last, last.c.last_id == SupportCaseComment.id)
        .where(SupportCaseComment.from_staff.is_(False))
    ).all()
    return {r[0] for r in rows}


def staff_detail(case: SupportCase) -> dict:
    item = as_dict(
        case,
        votes=_votes([case.id]).get(case.id, 0),
        comments=_comment_counts([case.id], staff=True).get(case.id, 0),
    )
    item["reporter"] = _reporter(
        case, db.session.get(User, case.user_id) if case.user_id else None
    )
    item["club"] = _clubs({case.tenant_id}).get(case.tenant_id)
    item["comments"] = comments_for(case, staff=True)
    merged = db.session.scalars(
        select(SupportCase)
        .where(SupportCase.merged_into_id == case.id)
        .order_by(SupportCase.id)
    ).all()
    item["merged"] = [
        {"id": m.id, "title": m.title, "createdAt": _iso(m.created_at)} for m in merged
    ]
    from hubra.core.services import support_discord

    item["people"] = support_discord.people_dicts(case)
    item["discord"] = {
        "enabled": support_discord.enabled(),
        "threadId": case.discord_thread_id,
        "threadUrl": support_discord.thread_url(case),
    }
    return item


def add_comment(
    case: SupportCase, user_id: int | None, body, *, staff: bool, internal: bool = False
) -> SupportCaseComment:
    text = _text(body, "body", COMMENT_MAX, required=True)
    comment = SupportCaseComment(
        case_id=case.id,
        user_id=user_id,
        body=text,
        from_staff=staff,
        internal=bool(staff and internal),
    )
    db.session.add(comment)
    case.updated_at = datetime.now(timezone.utc)
    db.session.flush()
    return comment


def set_status(case: SupportCase, status: str) -> bool:
    """True when the status changed."""
    if status not in STATUSES:
        raise SupportError("Unknown status")
    if case.merged_into_id is not None and status != "closed":
        raise SupportError("A merged case stays closed")
    if status == case.status:
        return False
    case.status = status
    case.closed_at = datetime.now(timezone.utc) if status in FINISHED else None
    return True


def edit(case: SupportCase, body: dict) -> list[str]:
    """Title, description, area, is_public, roadmap_item.  Returns the
    changed fields."""
    changed: list[str] = []
    if "title" in body:
        title = _text(body["title"], "title", TITLE_MAX, required=True)
        if title != case.title:
            case.title = title
            changed.append("title")
    if "description" in body:
        text = _text(body["description"], "description", TEXT_MAX, required=True)
        if text != case.description:
            case.description = text
            changed.append("description")
    if "area" in body:
        area = body["area"]
        if area is not None and area not in AREAS:
            raise SupportError("Unknown area")
        if area != case.area:
            case.area = area
            changed.append("area")
    if "isPublic" in body:
        public = body["isPublic"]
        if not isinstance(public, bool):
            raise SupportError("isPublic must be true or false")
        if public and case.kind != "feature":
            raise SupportError("Only feature requests go on the roadmap")
        if public and case.merged_into_id is not None:
            raise SupportError("A merged case cannot go on the roadmap")
        if public != case.is_public:
            case.is_public = public
            changed.append("isPublic")
    if "roadmapItem" in body:
        item = body["roadmapItem"] or None
        if item is not None:
            if case.kind != "feature":
                raise SupportError("Only feature requests go on the roadmap")
            if not isinstance(item, str) or item not in {p["id"] for p in _plan()}:
                raise SupportError("Unknown roadmap item")
        if item != case.roadmap_item:
            case.roadmap_item = item
            changed.append("roadmapItem")
    return changed


def merge(source: SupportCase, target: SupportCase, actor_id: int | None) -> None:
    """Fold *source* into *target*: votes move, source closes and points there."""
    if source.id == target.id:
        raise SupportError("A case cannot be merged into itself")
    if source.kind != target.kind:
        raise SupportError("Only cases of the same kind can be merged")
    if source.merged_into_id is not None:
        raise SupportError("This case was merged already")
    if target.merged_into_id is not None:
        raise SupportError("The target was merged into another case")

    target_voters = set(
        db.session.scalars(
            select(SupportCaseVote.user_id).where(SupportCaseVote.case_id == target.id)
        ).all()
    )
    for v in db.session.scalars(
        select(SupportCaseVote).where(SupportCaseVote.case_id == source.id)
    ).all():
        if v.user_id in target_voters:
            db.session.delete(v)
        else:
            v.case_id = target.id
            target_voters.add(v.user_id)
    if (
        source.kind == "feature"
        and source.user_id
        and source.user_id not in target_voters
    ):
        db.session.add(SupportCaseVote(case_id=target.id, user_id=source.user_id))
    # Cases merged into the source before go to the target too.
    for earlier in db.session.scalars(
        select(SupportCase).where(SupportCase.merged_into_id == source.id)
    ).all():
        earlier.merged_into_id = target.id

    if source.roadmap_item and not target.roadmap_item:
        target.roadmap_item = source.roadmap_item
    source.merged_into_id = target.id
    source.is_public = False
    source.roadmap_item = None
    set_status(source, "closed")
    now = datetime.now(timezone.utc)
    source.updated_at = now
    target.updated_at = now
    db.session.add(
        SupportCaseComment(
            case_id=target.id,
            user_id=actor_id,
            body=f"#{source.id} merged into this case: {source.title}",
            from_staff=True,
            internal=True,
        )
    )
    db.session.flush()


def followers(case: SupportCase) -> list[User]:
    """Who hears about a status change or an answer: the reporter, the
    people staff added, and the reporters of cases merged into it."""
    ids = (
        {case.user_id}
        | set(
            db.session.scalars(
                select(SupportCase.user_id).where(
                    SupportCase.merged_into_id == case.id
                )
            ).all()
        )
        | set(
            db.session.scalars(
                select(SupportCasePerson.user_id).where(
                    SupportCasePerson.case_id == case.id
                )
            ).all()
        )
    )
    ids.discard(None)
    if not ids:
        return []
    return list(
        db.session.scalars(
            select(User).where(User.id.in_(ids)).where(User.is_disabled.is_(False))
        ).all()
    )


# ── Messages ──────────────────────────────────────────────────────────────────


def _guest_line(case: SupportCase) -> str:
    guest = guest_contact(case)
    if guest is None:
        return "From: unknown"
    who = f"{guest['name']} <{guest['email']}>" if guest.get("name") else guest["email"]
    line = f"From: {who} (no account, {guest.get('reason', 'other')})"
    return line + (f", mail: {guest['mail']}" if guest.get("mail") else "")


def alert_staff(case: SupportCase) -> None:
    """Tell platform admins about a new case.  Never raises."""
    try:
        from hubra.core.services import platform_monitor

        reporter = db.session.get(User, case.user_id) if case.user_id else None
        club = _clubs({case.tenant_id}).get(case.tenant_id)
        label = "Problem report" if case.kind == "bug" else "Feature request"
        fp = case.fingerprint or {}
        device = " ".join(
            str(p)
            for p in (
                fp.get("browser"),
                fp.get("browserVersion"),
                "on" if fp.get("os") else None,
                fp.get("os"),
                f"({fp['deviceType']})" if fp.get("deviceType") else None,
            )
            if p
        )
        lines = [
            f"{label} #{case.id}: {case.title}",
            f"From: {reporter.name} <{reporter.email}>"
            if reporter
            else _guest_line(case),
        ]
        if club:
            lines.append(f"Club: {club['name']}")
        if case.severity:
            lines.append(f"Severity: {case.severity}")
        if case.page:
            lines.append(f"Page: {case.page}")
        if device:
            lines.append(f"Device: {device}")
        lines.append("")
        lines.append(case.description[:600])
        platform_monitor.alert(
            "support_cases",
            f"New {label.lower()}: {case.title}",
            lines,
            level="warning" if case.severity == "blocking" else "info",
            throttle=False,
        )
    except Exception:  # noqa: BLE001
        logger.warning("support_case_alert_failed id=%s", case.id, exc_info=True)


def mail_update(
    case: SupportCase,
    users: list[User],
    *,
    comment: str | None = None,
    merged_into: SupportCase | None = None,
) -> int:
    """Mail *users* that staff answered (*comment*), changed the status or
    merged the case (*merged_into*)."""
    from hubra.core.services import email

    from hubra.core.notifications import account_dm

    sent = 0
    for user in users:
        try:
            account_dm.support_case_update(
                user, case, comment=comment, merged_into=merged_into
            )
        except Exception:  # noqa: BLE001
            logger.warning("support_case_dm_failed id=%s", case.id, exc_info=True)
        try:
            if email.send_support_case_update(
                user.email,
                user.name or user.email,
                case_id=case.id,
                kind=case.kind,
                title=case.title,
                status=case.status,
                comment=comment,
                merged_into=(
                    f"#{merged_into.id} {merged_into.title}" if merged_into else None
                ),
                lang=user.language or email.DEFAULT_LANG,
            ):
                sent += 1
        except Exception:  # noqa: BLE001
            logger.warning("support_case_mail_failed id=%s", case.id, exc_info=True)
    guest = guest_contact(case)
    if guest is not None:
        # A guest has no account to read answers in: the mail is all they get.
        try:
            if email.send_support_case_update(
                guest["email"],
                guest.get("name") or guest["email"],
                case_id=case.id,
                kind=case.kind,
                title=case.title,
                status=case.status,
                comment=comment,
                merged_into=(
                    f"#{merged_into.id} {merged_into.title}" if merged_into else None
                ),
                lang=email.DEFAULT_LANG,
                with_link=False,
            ):
                sent += 1
        except Exception:  # noqa: BLE001
            logger.warning("support_case_guest_mail_failed id=%s", case.id, exc_info=True)
    return sent
