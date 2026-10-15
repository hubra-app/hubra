"""InventoryItem model, InventoryCheckout model, and item_instructions association table."""

from __future__ import annotations

from datetime import date, datetime, timezone

import sqlalchemy as sa
from sqlalchemy import Column, Date, DateTime, ForeignKey, JSON, Table, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vollbuild.core.extensions import db


# ── Association table ─────────────────────────────────────────────────────────

item_instructions = Table(
    "item_instructions",
    db.metadata,
    Column(
        "item_id",
        db.Integer,
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "member_id",
        db.Integer,
        ForeignKey("members.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "instructed_at",
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    ),
)


# ── InventoryItem ─────────────────────────────────────────────────────────────

_CATEGORIES = ("Tool", "Item", "Material")
_STATUSES = (
    "available",
    "in_use",
    "maintenance",
    "broken",
    "archived",
    "checked_out",
    "pending",
    "lost",
    "retired",
)
_VISIBILITIES = ("private", "shared")


class InventoryItem(db.Model):
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    # "Tool" | "Item" | "Material"
    category: Mapped[str] = mapped_column(db.String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    owner_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    responsible_id: Mapped[int | None] = mapped_column(
        db.Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )

    # "private" | "shared"
    visibility: Mapped[str] = mapped_column(
        db.String(20), nullable=False, default="shared"
    )
    # "available" | "in_use" | "maintenance" | "broken" | "archived" | "checked_out" | "pending" | "lost" | "retired"
    status: Mapped[str] = mapped_column(
        db.String(30), nullable=False, default="available"
    )

    cost: Mapped[float | None] = mapped_column(db.Numeric(10, 2), nullable=True)
    # [{"label": "Supplier", "url": "https://..."}, ...]
    links: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list, server_default=sa.text("'[]'")
    )

    instruction_required: Mapped[bool] = mapped_column(
        db.Boolean, nullable=False, default=False
    )

    # M5 new fields
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    purchase_cost: Mapped[float | None] = mapped_column(
        db.Numeric(10, 2), nullable=True
    )
    current_value: Mapped[float | None] = mapped_column(
        db.Numeric(10, 2), nullable=True
    )
    location: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    barcode_id: Mapped[str | None] = mapped_column(db.String(255), nullable=True)
    # [{"name": "Manual", "url": "https://...", "type": "pdf"}, ...]
    documents: Mapped[list | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True, default=list
    )
    image_url: Mapped[str | None] = mapped_column(db.String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
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
    owner: Mapped["Member | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member", foreign_keys=[owner_id]
    )
    responsible: Mapped["Member | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member", foreign_keys=[responsible_id]
    )
    instructed_members: Mapped[list["Member"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member",
        secondary=item_instructions,
        back_populates="instructed_items",
    )
    checkouts: Mapped[list["InventoryCheckout"]] = relationship(
        "InventoryCheckout",
        back_populates="item",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<InventoryItem id={self.id} name={self.name!r}>"


class InventoryCheckout(db.Model):
    """Track check-out/check-in history for inventory items."""

    __tablename__ = "inventory_checkouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[int] = mapped_column(
        db.Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    checked_out_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    expected_return_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    returned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    condition_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    item: Mapped["InventoryItem"] = relationship(
        "InventoryItem", back_populates="checkouts", foreign_keys=[item_id]
    )
    member: Mapped["Member"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Member", foreign_keys=[member_id]
    )

    def __repr__(self) -> str:
        return f"<InventoryCheckout item_id={self.item_id} member_id={self.member_id}>"
