"""Which poster brought people: the source tag of a join or trial poster's
QR code (``?src=``) travels with the request to join or the trial booking,
and one row per sign-up (no one's details) keeps the count."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from hubra.core.extensions import db

KINDS = ("join", "trial")
_TAG = re.compile(r"[^a-z0-9-]+")


def clean(value) -> str | None:
    """A source tag: lower case letters, digits and dashes, at most 40
    characters; anything else (or nothing) is None."""
    if not isinstance(value, str):
        return None
    tag = _TAG.sub("-", value.strip().lower()).strip("-")[:40].strip("-")
    return tag or None


def record(kind: str, source: str | None) -> None:
    """Count one sign-up from *source* (nothing without one)."""
    from hubra.core.models.application import SignupSource

    if source and kind in KINDS:
        db.session.add(SignupSource(kind=kind, source=source))


def summary(days: int = 365) -> list[dict]:
    """Sign-ups per source over the last *days*, most first:
    ``[{source, join, trial}]``."""
    from hubra.core.models.application import SignupSource

    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.session.execute(
        select(SignupSource.source, SignupSource.kind, func.count())
        .where(SignupSource.created_at >= since)
        .group_by(SignupSource.source, SignupSource.kind)
    ).all()
    out: dict[str, dict] = {}
    for source, kind, count in rows:
        out.setdefault(source, {"source": source, "join": 0, "trial": 0})[kind] = count
    return sorted(out.values(), key=lambda r: (-(r["join"] + r["trial"]), r["source"]))
