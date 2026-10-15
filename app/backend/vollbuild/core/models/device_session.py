"""Device and Session models — multi-device login tracking and session revocation.

Device tracks a physical browser (identified by a stable fingerprint of
browser family + platform).  Session tracks an individual JWT login,
linked to a Device.  One Device can have many Sessions over time.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vollbuild.core.extensions import db


class Device(db.Model):
    """A browser/device used to log in, identified by a stable fingerprint.

    The fingerprint is derived from browser family + platform (e.g.
    "Chrome on Windows") and does NOT include version numbers, so it stays
    stable across browser updates.
    """

    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint("member_id", "fingerprint", name="uq_member_fingerprint"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    fingerprint: Mapped[str] = mapped_column(db.String(64), nullable=False, index=True)
    browser_family: Mapped[str | None] = mapped_column(db.String(50), nullable=True)
    platform: Mapped[str | None] = mapped_column(db.String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(db.String(512), nullable=True)
    name: Mapped[str | None] = mapped_column(db.String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="device", cascade="all, delete-orphan"
    )
    member: Mapped["Member"] = relationship("Member")  # type: ignore[name-defined]  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<Device id={self.id} member_id={self.member_id} fp={self.fingerprint!r}>"
        )


class Session(db.Model):
    """A single JWT login session, linked to a Device.

    When a user logs in, a Session is created (or an existing active one
    for the same Device is reused).  Revoking a Session invalidates the
    JWT without deleting the Device.
    """

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    jti: Mapped[str] = mapped_column(db.String(255), unique=True, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(db.String(45), nullable=True)
    create_reason: Mapped[str | None] = mapped_column(db.String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_reason: Mapped[str | None] = mapped_column(db.String(50), nullable=True)

    device: Mapped["Device"] = relationship("Device", back_populates="sessions")

    def __repr__(self) -> str:
        return f"<Session id={self.id} device_id={self.device_id} jti={self.jti!r}>"

    @staticmethod
    def active_session_count(device_id: int) -> int:
        return (
            db.session.scalar(
                select(func.count(Session.id)).where(
                    Session.device_id == device_id,
                    Session.revoked_at.is_(None),
                )
            )
            or 0
        )
