"""The "shipped" mails: tell the people who wanted a roadmap item that it is out.

A roadmap item (ROADMAP.yaml) that is ``done`` with a ``version`` shipped in
that Hubra release.  Once that version runs, everyone who wanted the item
gets one short mail:

* who voted for it on the roadmap (``roadmap_votes``);
* who voted for an idea linked to it (``support_case_votes``);
* who reported such an idea (the reporter's vote counts once it is public,
  but an idea that was linked before it went public has none).

``notify`` runs on every changelog tick (``changelogs.announce``) for the
version that runs now, so an item that gets its ``version`` in a later
deploy of the same release still goes out.  "Sent" is a
``roadmap.shipped`` row in the platform log per item id, written before the
mails are queued: an item is mailed once, also after a rollback.  The
mails go out from a worker after the commit.

The What's new dialog shows the same items on their release for those who
voted (the roadmap's ``voted`` flag), so this module has no read side.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from hubra.core.extensions import db

_log = logging.getLogger(__name__)

SENT = "roadmap.shipped"


def items_for(version: str) -> list[dict]:
    """The roadmap items that shipped in *version*."""
    from hubra.core.services.version import VersionService

    wanted = str(version).strip().lstrip("v")
    return [
        item
        for item in VersionService.get_roadmap()
        if item["status"] == "done"
        and str(item.get("version") or "").strip().lstrip("v") == wanted
    ]


def audience(item_id: str) -> list[int]:
    """Ids of the people who wanted *item_id*: its voters, and the voters and
    reporters of the ideas linked to it (merged ideas count through the one
    they were merged into)."""
    from hubra.core.models.support_case import (
        RoadmapVote,
        SupportCase,
        SupportCaseVote,
    )
    from hubra.core.models.user import User

    people = set(
        db.session.scalars(
            select(RoadmapVote.user_id).where(RoadmapVote.item == item_id)
        ).all()
    )
    cases = db.session.execute(
        select(SupportCase.id, SupportCase.user_id)
        .where(SupportCase.kind == "feature")
        .where(SupportCase.roadmap_item == item_id)
    ).all()
    case_ids = [cid for cid, _ in cases]
    people |= {uid for _, uid in cases if uid is not None}
    if case_ids:
        people |= set(
            db.session.scalars(
                select(SupportCaseVote.user_id).where(
                    SupportCaseVote.case_id.in_(case_ids)
                )
            ).all()
        )
    if not people:
        return []
    return sorted(
        db.session.scalars(
            select(User.id)
            .where(User.id.in_(people))
            .where(User.is_disabled.is_(False))
        ).all()
    )


def _sent_items() -> set[str]:
    from hubra.core.models.platform_event import PlatformEvent

    return set(
        db.session.scalars(
            select(PlatformEvent.message).where(PlatformEvent.kind == SENT)
        ).all()
    )


def _mark(item_id: str, version: str, people: int) -> None:
    from hubra.core.models.platform_event import PlatformEvent

    db.session.add(
        PlatformEvent(
            created_at=datetime.now(timezone.utc),
            category="system",
            kind=SENT,
            level="info",
            message=item_id,
            details={"version": version, "people": people},
        )
    )


def notify(version: str | None) -> int:
    """Queue the mails for every item of *version* not sent yet. Commits.
    Returns how many items went out."""
    if not version:
        return 0
    items = [i for i in items_for(version) if i["id"] not in _sent_items()]
    if not items:
        return 0
    from hubra.core.tasks.after_commit import delay_after_commit
    from hubra.core.tasks.platform_bot_tasks import send_shipped_mails

    for item in items:
        people = audience(item["id"])
        _mark(item["id"], str(version), len(people))
        if people:
            delay_after_commit(send_shipped_mails, item["id"], str(version), people)
        _log.info("shipped: %s in %s to %d people", item["id"], version, len(people))
    db.session.commit()
    return len(items)


def _pick(texts: dict | None, lang: str) -> str:
    texts = texts or {}
    return texts.get(lang) or texts.get("en") or texts.get("de") or ""


def send_mails(item_id: str, version: str, user_ids: list[int]) -> int:
    """Mail each of *user_ids* that *item_id* shipped in *version*. Returns
    how many mails went out."""
    from hubra.core.models.user import User
    from hubra.core.services import email
    from hubra.core.services.version import VersionService

    item = next((i for i in VersionService.get_roadmap() if i["id"] == item_id), None)
    if item is None:
        return 0
    sent = 0
    for user in db.session.scalars(select(User).where(User.id.in_(user_ids))).all():
        lang = "en" if (user.language or "").startswith("en") else "de"
        try:
            if email.send_roadmap_shipped(
                user.email,
                user.name or user.email,
                title=_pick(item.get("title"), lang),
                summary=_pick(item.get("summary"), lang),
                version=version,
                lang=user.language or email.DEFAULT_LANG,
            ):
                sent += 1
        except Exception:  # noqa: BLE001
            _log.warning(
                "shipped_mail_failed item=%s user=%s", item_id, user.id, exc_info=True
            )
    return sent
