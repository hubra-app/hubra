"""Inventory service — business logic for inventory items, instructions, and checkouts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import selectinload

from hubra.api.utils import log_audit
from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.models.inventory import (
    InventoryCheckout,
    InventoryItem,
    item_instructions,
)
from hubra.core.models.member import Member


def _has_overdue_invoice(member_id: int, grace_days: int = 7) -> bool:
    """True when the member has an unpaid invoice more than *grace_days* late."""
    from datetime import date

    from hubra.core.models.finance import Invoice

    cutoff = date.today() - timedelta(days=grace_days)
    return (
        db.session.scalar(
            select(Invoice.id)
            .where(Invoice.member_id == member_id)
            .where(Invoice.status == "Open")
            .where(Invoice.due <= cutoff)
            .limit(1)
        )
        is not None
    )


_LOAD_OPTS = [
    selectinload(InventoryItem.owner),
    selectinload(InventoryItem.responsible),
    selectinload(InventoryItem.instructed_members),
]


class InventoryService:
    """Operations on a single inventory item."""

    @staticmethod
    def get(item_id: int) -> InventoryItem:
        """Return an inventory item with relations loaded, or raise 404."""
        item = db.session.scalar(
            select(InventoryItem)
            .where(InventoryItem.id == item_id)
            .options(*_LOAD_OPTS)
        )
        if item is None:
            raise_error(404, "NOT_FOUND", f"Inventory item {item_id} not found")
        return item  # type: ignore[return-value]

    @staticmethod
    def update(item: InventoryItem, data: dict, actor_id: int) -> InventoryItem:
        """Update allowed fields on an inventory item."""
        for field in (
            "name",
            "category",
            "description",
            "owner_id",
            "responsible_id",
            "visibility",
            "status",
            "cost",
            "links",
            "instruction_required",
            "purchase_date",
            "purchase_cost",
            "current_value",
            "location",
            "serial_number",
            "barcode_id",
            "documents",
            "image_url",
            "notes",
        ):
            if field in data:
                setattr(item, field, data[field])

        log_audit(
            actor_id=actor_id,
            action="update_inventory_item",
            target_type="InventoryItem",
            target_id=item.id,
            target_label=item.name,
        )
        return item

    @staticmethod
    def delete(item_id: int, actor_id: int) -> None:
        """Delete an inventory item."""
        item = InventoryService.get(item_id)

        log_audit(
            actor_id=actor_id,
            action="delete_inventory_item",
            target_type="InventoryItem",
            target_id=item.id,
            target_label=item.name,
        )
        db.session.delete(item)

    @staticmethod
    def add_instruction(item: InventoryItem, member: Member) -> None:
        """Record a member being instructed on an item. Raises 409 if already."""
        already = db.session.scalar(
            select(func.count())
            .select_from(item_instructions)
            .where(
                item_instructions.c.item_id == item.id,
                item_instructions.c.member_id == member.id,
            )
        )
        if already:
            raise_error(
                409,
                "CONFLICT",
                f"Member {member.id} is already instructed on item {item.id}",
            )

        db.session.execute(
            insert(item_instructions).values(
                item_id=item.id,
                member_id=member.id,
                instructed_at=datetime.now(timezone.utc),
            )
        )

    @staticmethod
    def remove_instruction(item_id: int, member_id: int) -> None:
        """Remove an instruction record. Raises 404 if not found."""
        exists = db.session.scalar(
            select(func.count())
            .select_from(item_instructions)
            .where(
                item_instructions.c.item_id == item_id,
                item_instructions.c.member_id == member_id,
            )
        )
        if not exists:
            raise_error(
                404,
                "NOT_FOUND",
                f"Member {member_id} has no instruction record for item {item_id}",
            )

        db.session.execute(
            delete(item_instructions).where(
                item_instructions.c.item_id == item_id,
                item_instructions.c.member_id == member_id,
            )
        )

    @staticmethod
    def checkout(
        item_id: int,
        member_id: int,
        expected_return_at: datetime | None = None,
        condition_notes: str | None = None,
        actor_id: int | None = None,
    ) -> InventoryCheckout:
        """Check out an item to a member. Raises 409 if not available."""
        item = InventoryService.get(item_id)

        if item.status not in ("available",):
            raise_error(
                409,
                "CONFLICT",
                f"Item {item_id} is not available for checkout (status: {item.status})",
            )

        member = db.session.get(Member, member_id)
        if member is None or member.archived_at is not None:
            raise_error(404, "NOT_FOUND", f"Member {member_id} not found")

        from hubra.core.modules import get_config, is_enabled

        config = get_config("inventory")
        if (
            config.get("require_induction")
            and item.instruction_required
            and member not in item.instructed_members
        ):
            raise_error(
                409,
                "NOT_INSTRUCTED",
                f"{member.name} has not been instructed on {item.name}",
            )
        if (
            config.get("block_when_overdue")
            and is_enabled("finance")
            and _has_overdue_invoice(member_id)
        ):
            raise_error(
                409,
                "PAYMENT_OVERDUE",
                f"{member.name} has an overdue invoice",
            )

        if expected_return_at is None:
            max_days = config.get("checkout_max_days") or 0
            if max_days > 0:
                expected_return_at = datetime.now(timezone.utc) + timedelta(
                    days=max_days
                )

        checkout = InventoryCheckout(
            item_id=item_id,
            member_id=member_id,
            expected_return_at=expected_return_at,
            condition_notes=condition_notes,
        )
        db.session.add(checkout)

        item.status = "checked_out"

        log_audit(
            actor_id=actor_id,
            action="checkout_inventory_item",
            target_type="InventoryItem",
            target_id=item.id,
            target_label=item.name,
        )
        return checkout

    @staticmethod
    def checkin(
        item_id: int, condition_notes: str | None = None, actor_id: int | None = None
    ) -> InventoryCheckout:
        """Check in an item. Raises 409 if not checked out."""
        item = InventoryService.get(item_id)

        if item.status != "checked_out":
            raise_error(
                409,
                "CONFLICT",
                f"Item {item_id} is not checked out",
            )

        checkout = db.session.scalar(
            select(InventoryCheckout)
            .where(
                InventoryCheckout.item_id == item_id,
                InventoryCheckout.returned_at.is_(None),
            )
            .order_by(InventoryCheckout.checked_out_at.desc())
        )
        if checkout is None:
            raise_error(
                404,
                "NOT_FOUND",
                f"No active checkout found for item {item_id}",
            )

        checkout.returned_at = datetime.now(timezone.utc)
        if condition_notes:
            checkout.condition_notes = condition_notes

        item.status = "available"

        log_audit(
            actor_id=actor_id,
            action="checkin_inventory_item",
            target_type="InventoryItem",
            target_id=item.id,
            target_label=item.name,
        )
        return checkout

    @staticmethod
    def list_overdue() -> list[InventoryCheckout]:
        """Return overdue checkouts (expected_return_at < now and not returned)."""
        now = datetime.now(timezone.utc)
        return db.session.scalars(
            select(InventoryCheckout)
            .where(InventoryCheckout.returned_at.is_(None))
            .where(InventoryCheckout.expected_return_at.isnot(None))
            .where(InventoryCheckout.expected_return_at < now)
            .options(
                selectinload(InventoryCheckout.item),
                selectinload(InventoryCheckout.member),
            )
        ).all()  # type: ignore[return-value]


class InventoryServiceItems:
    """Operations on the inventory collection."""

    @staticmethod
    def list(
        category: str = "",
        status: str = "",
        visibility: str = "",
    ) -> list[InventoryItem]:
        """Return inventory items with optional filters."""
        query = select(InventoryItem).options(*_LOAD_OPTS).order_by(InventoryItem.name)

        if category:
            query = query.where(InventoryItem.category == category)
        if status:
            query = query.where(InventoryItem.status == status)
        if visibility:
            query = query.where(InventoryItem.visibility == visibility)

        return db.session.scalars(query).all()  # type: ignore[return-value]

    @staticmethod
    def create(data: dict, actor_id: int) -> InventoryItem:
        """Create a new inventory item."""
        item = InventoryItem(
            name=data["name"],
            category=data["category"],
            description=data.get("description"),
            owner_id=data.get("owner_id"),
            responsible_id=data.get("responsible_id"),
            visibility=data.get("visibility", "shared"),
            status=data.get("status", "available"),
            cost=data.get("cost"),
            links=data.get("links") or [],
            instruction_required=data.get("instruction_required", False),
            purchase_date=data.get("purchase_date"),
            purchase_cost=data.get("purchase_cost"),
            current_value=data.get("current_value"),
            location=data.get("location"),
            serial_number=data.get("serial_number"),
            barcode_id=data.get("barcode_id"),
            documents=data.get("documents") or [],
            image_url=data.get("image_url"),
            notes=data.get("notes"),
        )
        db.session.add(item)
        db.session.flush()

        log_audit(
            actor_id=actor_id,
            action="create_inventory_item",
            target_type="InventoryItem",
            target_id=item.id,
            target_label=item.name,
        )

        db.session.refresh(item)
        return InventoryService.get(item.id)
