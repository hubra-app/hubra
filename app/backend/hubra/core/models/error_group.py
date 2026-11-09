"""ErrorGroup: unexpected server errors of the API, one row per kind.

Public schema only.  Errors with the same exception type, route and place
in Hubra's code are one group; the row keeps how often it happened, the
latest message and traceback, the first and last build it happened on, and
a count per build.  Shown in manage › Diagnose › Fehler
(``services.error_tracker``).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from hubra.core.extensions import db


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ErrorGroup(db.Model):
    __tablename__ = "error_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    exc_type: Mapped[str] = mapped_column(String(200), nullable=False)
    route: Mapped[str] = mapped_column(String(300), nullable=False)
    # Hubra's innermost frame: "hubra/api/members/services.py in add_account".
    location: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    traceback: Mapped[str] = mapped_column(Text, nullable=False, default="")
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, index=True
    )
    first_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    first_commit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_commit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # {"0.6.1 (abc1234)": 12, ...}
    builds: Mapped[dict | None] = mapped_column(
        JSONB().with_variant(db.JSON, "sqlite"), nullable=True
    )
    last_tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # open | resolved; a resolved group that happens again opens again.
    # resolved_by is empty when an upgrade resolved it (error_tracker
    # .resolve_after_upgrade); resolved_build is the build it was fixed in.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolved_build: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reopened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
