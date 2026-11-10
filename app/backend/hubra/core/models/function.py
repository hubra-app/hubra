"""Function/Office model — single-office-holder roles (Kassier, Präsidium, etc.)."""

from __future__ import annotations

from datetime import date, datetime, timezone

import sqlalchemy as sa
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hubra.core.extensions import db


# The roles a function gives its holders while their term runs (Kassier/in
# gives Vorstand and Treasurer). Replaces the single grants_tenant_role_id.
function_roles = db.Table(
    "function_roles",
    db.Column(
        "function_id",
        db.Integer,
        ForeignKey("functions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "role_id",
        db.Integer,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)


class Function(db.Model):
    """A club function/office with one or more holders (e.g. Kassier).

    Distinct from Role (RBAC permission bundling) and Group (multi-member
    collaboration). A Function tracks *who currently holds an office* and
    optionally provides a managed mail alias that forwards to the holder.
    """

    __tablename__ = "functions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(db.Text, nullable=True)
    max_holders: Mapped[int] = mapped_column(db.Integer, default=1, nullable=False)
    # Stable name of a standard function ("president", "treasurer", ...),
    # so upgrades find it whatever the club renamed it to.
    key: Mapped[str | None] = mapped_column(String(50), unique=True, index=True, nullable=True)
    # Legacy: the one role a function gave before function_roles. Copied into
    # function_roles by migration e3a7c9f1b5d2 and no longer read.
    grants_tenant_role_id: Mapped[int | None] = mapped_column(
        db.Integer,
        ForeignKey("roles.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Reference to a managed mail address for this function
    mailbox_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # A group function (Trainer/in, Gruppenkassier/in): its holders hold it
    # for one group each, and its roles count in that group only.
    per_group: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa.text("false")
    )
    # Enforces max_holders=1 at the model level
    is_singleton: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa.text("false")
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

    roles: Mapped[list["Role"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Role", secondary=function_roles, order_by="Role.name"
    )
    holders: Mapped[list["FunctionHolder"]] = relationship(
        "FunctionHolder",
        back_populates="function",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Function id={self.id} name={self.name!r}>"


class FunctionHolder(db.Model):
    """Association between a Function and the Member currently holding it."""

    __tablename__ = "function_holders"
    # A club function once per member; a group function once per member and
    # group (migration f4c2a8e6b1d3 replaced the unique function + member).
    __table_args__ = (
        db.Index(
            "uq_function_holders_club",
            "function_id",
            "member_id",
            unique=True,
            postgresql_where=sa.text("group_id IS NULL"),
            sqlite_where=sa.text("group_id IS NULL"),
        ),
        db.Index(
            "uq_function_holders_group",
            "function_id",
            "member_id",
            "group_id",
            unique=True,
            postgresql_where=sa.text("group_id IS NOT NULL"),
            sqlite_where=sa.text("group_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    function_id: Mapped[int] = mapped_column(
        db.Integer,
        ForeignKey("functions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    member_id: Mapped[int] = mapped_column(
        db.Integer,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    # The group a group function is held for; None for a club function.
    group_id: Mapped[int | None] = mapped_column(
        db.Integer,
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    term_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    term_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    function: Mapped["Function"] = relationship("Function", back_populates="holders")
    group: Mapped["Group | None"] = relationship("Group")  # type: ignore[name-defined]  # noqa: F821
    member: Mapped["Member"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member", backref="function_holders"
    )

    def __repr__(self) -> str:
        return f"<FunctionHolder function_id={self.function_id} member_id={self.member_id}>"
