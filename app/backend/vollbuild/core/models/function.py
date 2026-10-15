"""Function/Office model — single-office-holder roles (Kassier, Präsidium, etc.)."""

from __future__ import annotations

from datetime import date, datetime, timezone

import sqlalchemy as sa
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vollbuild.core.extensions import db


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
    # A Function can auto-grant a tenant role to its holder
    grants_tenant_role_id: Mapped[int | None] = mapped_column(
        db.Integer,
        ForeignKey("roles.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Reference to a managed mail address for this function
    mailbox_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
    __table_args__ = (UniqueConstraint("function_id", "member_id"),)

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
    term_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    term_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    function: Mapped["Function"] = relationship("Function", back_populates="holders")
    member: Mapped["Member"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member", backref="function_holders"
    )

    def __repr__(self) -> str:
        return f"<FunctionHolder function_id={self.function_id} member_id={self.member_id}>"
