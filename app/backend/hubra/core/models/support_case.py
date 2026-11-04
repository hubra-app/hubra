"""Support cases: problem reports and feature requests from the app.

Stored in the public schema, like club requests: a case belongs to the
person who sent it (and names the club they were in), and platform staff
handle it in manage › Support.

* ``kind`` is ``bug`` (a problem) or ``feature`` (an idea).
* ``status``: ``open`` → ``planned`` → ``in_progress`` → ``done``, or
  ``closed`` (not done: duplicate, won't fix, cannot reproduce).
* ``fingerprint`` is what the app sends along on its own: browser and
  version, OS, device type, screen and window size, language and theme.
  Nothing else (``services.clean_fingerprint`` drops other keys).
* A feature request can be put on the public roadmap (``is_public``); people
  vote for those (``support_case_votes``).
* Duplicates are merged: the case points at the one it went into
  (``merged_into_id``), its votes move there, and it is closed.
* Comments are visible to the reporter unless ``internal`` (staff notes).
* Staff can link an idea to an item of the planned roadmap (``roadmap_item``,
  an ``id`` from ROADMAP.yaml): the idea then shows as that item on the one
  public roadmap, and its votes count for it.  People can also vote for a
  planned item directly (``roadmap_votes``).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    false,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SupportCase(db.Model):
    __tablename__ = "support_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="open", server_default="open", index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # The form's other answers: steps, expected (bug) or use_case (feature).
    details: Mapped[dict | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )
    area: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Bugs: minor | annoying | blocking.
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # The app page the report was sent from (path only, no query).
    page: Mapped[str | None] = mapped_column(String(300), nullable=True)
    fingerprint: Mapped[dict | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )
    user_id: Mapped[int | None] = mapped_column(
        db.Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tenant_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True
    )
    # ROADMAP.yaml item this idea is part of (see the module docstring).
    roadmap_item: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    merged_into_id: Mapped[int | None] = mapped_column(
        db.Integer,
        ForeignKey("support_cases.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


class SupportCaseComment(db.Model):
    __tablename__ = "support_case_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(
        db.Integer,
        ForeignKey("support_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Written by platform staff (in manage), not the reporter.
    from_staff: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    # A staff note the reporter never sees.
    internal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class SupportCaseVote(db.Model):
    __tablename__ = "support_case_votes"
    __table_args__ = (
        UniqueConstraint("case_id", "user_id", name="uq_support_case_vote"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(
        db.Integer,
        ForeignKey("support_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class RoadmapVote(db.Model):
    """A vote for a planned roadmap item (ROADMAP.yaml ``id``)."""

    __tablename__ = "roadmap_votes"
    __table_args__ = (UniqueConstraint("item", "user_id", name="uq_roadmap_vote"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    item: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
