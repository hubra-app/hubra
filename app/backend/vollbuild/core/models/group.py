"""Group model — project/interest groups within the makerspace."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vollbuild.core.extensions import db
from vollbuild.core.models.member import member_groups


class Group(db.Model):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(255), unique=True, nullable=False)
    lead_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("members.id"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(db.String(7), nullable=True)
    icon_name: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    # e.g. "3x/week"
    sessions: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    tools: Mapped[int] = mapped_column(db.Integer, default=0, nullable=False)
    is_default: Mapped[bool] = mapped_column(db.Boolean, default=False, nullable=False)
    # M5 fields
    # board | committee | team | interest_group | mailing_list
    type: Mapped[str] = mapped_column(
        db.String(50), default="interest_group", nullable=False
    )
    email_alias: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    is_public: Mapped[bool] = mapped_column(db.Boolean, default=True, nullable=False)
    # Members may join and leave on their own (interest groups).
    self_join: Mapped[bool] = mapped_column(
        db.Boolean, default=False, server_default=sa.false(), nullable=False
    )
    parent_group_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("groups.id"), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    lead: Mapped["Member | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member", foreign_keys=[lead_id], back_populates="led_groups"
    )
    members: Mapped[list["Member"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member",
        secondary=member_groups,
        back_populates="groups",
    )
    parent_group: Mapped["Group | None"] = relationship(
        "Group",
        remote_side="Group.id",
        foreign_keys=[parent_group_id],
    )
    child_groups: Mapped[list["Group"]] = relationship(
        "Group",
        foreign_keys=[parent_group_id],
        back_populates="parent_group",
    )
    memberships: Mapped[list["GroupMembership"]] = relationship(
        "GroupMembership",
        back_populates="group",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Group id={self.id} name={self.name!r}>"


class GroupMembership(db.Model):
    """Rich membership model with role, joined_at, and notes."""

    __tablename__ = "group_memberships"
    __table_args__ = (
        UniqueConstraint("group_id", "member_id", name="uq_group_member"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    # leader | member | treasurer | secretary
    role: Mapped[str] = mapped_column(db.String(50), default="member", nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    group: Mapped["Group"] = relationship(
        "Group", back_populates="memberships", foreign_keys=[group_id]
    )
    member: Mapped["Member"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member", foreign_keys=[member_id]
    )

    def __repr__(self) -> str:
        return f"<GroupMembership group_id={self.group_id} member_id={self.member_id} role={self.role!r}>"
