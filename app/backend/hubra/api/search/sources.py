"""What Hubra's own modules offer the club search (``<module>.search``).

Each handler finds at most ``data.limit`` things matching every word of
``data.q`` (case ignored) that the viewer may see; the contract's right
(``members.members.read`` and so on) is checked before it runs.
"""

from __future__ import annotations

from sqlalchemy import or_, select

from hubra.core.contracts.search import SearchHits, SearchIn
from hubra.core.extensions import db
from hubra.core.utils import escape_like


def _like(column, word: str):
    return column.ilike(f"%{escape_like(word)}%", escape="\\")


def _all_words(data: SearchIn, *columns):
    """Every word in one of *columns*."""
    return [or_(*(_like(c, w) for c in columns)) for w in data.words()]


def members(ctx, data: SearchIn) -> SearchHits:
    from hubra.api.members.services import _apply_member_filters
    from hubra.core.models.member import Member
    from hubra.core.models.user import User
    from hubra.core.permissions import _get_member_permission_keys, member_is_admin

    viewer = ctx.actor
    # Contact data may be hidden from the directory: by it only for those
    # who see it all (as the member list).
    sees_all = viewer is not None and (
        member_is_admin(viewer)
        or "members.members.update" in _get_member_permission_keys(viewer)
    )
    args = {"search": " ".join(data.words())}
    if not sees_all:
        args["search_names_only"] = "1"
    query = (
        select(Member, User)
        .join(User, Member.user_id == User.id)
        .where(Member.archived_at.is_(None), Member.deleted_at.is_(None))
        .order_by(User.last_name, User.first_name)
        .limit(data.limit)
    )
    query = _apply_member_filters(query, args)
    hits = []
    for member, user in db.session.execute(query):
        name = " ".join(p for p in (user.first_name, user.last_name) if p) or "?"
        hits.append(
            {
                "id": f"member:{member.id}",
                "label": name,
                "sub": member.tier.name if member.tier else None,
                "path": f"/app/members/{member.id}",
                "kind": "member",
            }
        )
    return SearchHits.model_validate({"hits": hits})


def groups(ctx, data: SearchIn) -> SearchHits:
    from hubra.core.models.group import Group

    rows = db.session.scalars(
        select(Group)
        .where(*_all_words(data, Group.name, Group.description))
        .order_by(Group.name)
        .limit(data.limit)
    )
    return SearchHits.model_validate(
        {
            "hits": [
                {
                    "id": f"group:{g.id}",
                    "label": g.name,
                    "sub": (g.description or "")[:120] or None,
                    "path": f"/app/groups/{g.id}",
                    "kind": "group",
                }
                for g in rows
            ]
        }
    )


def events(ctx, data: SearchIn) -> SearchHits:
    from hubra.api.events.services import event_link
    from hubra.core.models.event import ClubEvent

    rows = db.session.scalars(
        select(ClubEvent)
        .where(*_all_words(data, ClubEvent.title, ClubEvent.location))
        .order_by(ClubEvent.date.desc())
        .limit(data.limit)
    )
    return SearchHits.model_validate(
        {
            "hits": [
                {
                    "id": f"event:{e.id}",
                    "label": e.title,
                    "sub": e.location,
                    "date": e.date,
                    "path": event_link(e.id),
                    "kind": "event",
                }
                for e in rows
            ]
        }
    )


def posts(ctx, data: SearchIn) -> SearchHits:
    from datetime import datetime, timezone

    from hubra.core.models.post import Post

    now = datetime.now(timezone.utc)
    rows = db.session.scalars(
        select(Post)
        .where(Post.shown(now))
        .where(*_all_words(data, Post.title, Post.summary))
        .order_by(Post.created_at.desc())
        .limit(data.limit)
    )
    return SearchHits.model_validate(
        {
            "hits": [
                {
                    "id": f"post:{p.id}",
                    "label": p.title,
                    "sub": (p.summary or "")[:120] or None,
                    "path": f"/app/operations/posts/{p.id}",
                    "kind": "post",
                }
                for p in rows
            ]
        }
    )


def polls(ctx, data: SearchIn) -> SearchHits:
    from hubra.core.models.poll import Poll

    rows = db.session.scalars(
        select(Poll)
        .where(*_all_words(data, Poll.question))
        .order_by(Poll.id.desc())
        .limit(data.limit)
    )
    return SearchHits.model_validate(
        {
            "hits": [
                {
                    "id": f"poll:{p.id}",
                    "label": p.question,
                    "sub": p.status,
                    "path": "/app/operations/polls",
                    "kind": "poll",
                }
                for p in rows
            ]
        }
    )


def invoices(ctx, data: SearchIn) -> SearchHits:
    """By number ("1234" or "#1234"), description, or who pays it."""
    from hubra.core.models.external_party import ExternalParty
    from hubra.core.models.finance import Invoice
    from hubra.core.models.member import Member
    from hubra.core.models.user import User

    conds = []
    for word in data.words():
        number = word.lstrip("#")
        alts = [
            _like(Invoice.description, word),
            _like(User.first_name, word),
            _like(User.last_name, word),
            _like(ExternalParty.name, word),
        ]
        if number.isdigit() and len(number) < 10:
            alts.append(Invoice.id == int(number))
        conds.append(or_(*alts))
    rows = db.session.execute(
        select(Invoice, User, ExternalParty)
        .outerjoin(Member, Member.id == Invoice.member_id)
        .outerjoin(User, User.id == Member.user_id)
        .outerjoin(ExternalParty, ExternalParty.id == Invoice.external_party_id)
        .where(*conds)
        .order_by(Invoice.issued.desc(), Invoice.id.desc())
        .limit(data.limit)
    )
    hits = []
    for inv, user, party in rows:
        who = (
            " ".join(p for p in (user.first_name, user.last_name) if p)
            if user is not None
            else (party.name if party is not None else "")
        )
        hits.append(
            {
                "id": f"invoice:{inv.id}",
                "label": f"#{inv.id} {who}".strip(),
                "sub": f"CHF {inv.amount:.2f}"
                + (f" · {inv.description[:80]}" if inv.description else ""),
                "date": inv.issued,
                "path": f"/app/finance/invoices/{inv.id}",
                "kind": "invoice",
            }
        )
    return SearchHits.model_validate({"hits": hits})
