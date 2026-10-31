"""Inventory service — business logic for inventory items, instructions, and checkouts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, insert, or_, select
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


# What the owner and the responsible person of an item may do with it
# without the club-wide right (inventory.items.<action>). Admins and role
# holders are not limited by this.
ITEM_ACTIONS: dict[str, tuple[str, ...]] = {
    "read": ("owner", "responsible"),
    "update": ("owner", "responsible"),
    "delete": ("owner",),
    "manage_instructions": ("owner", "responsible"),
    "checkout": ("owner", "responsible"),
    "checkin": ("owner", "responsible"),
}
# Who has the item and who looks after it: only the owner hands these on.
OWNER_FIELDS = ("owner_id", "responsible_id", "visibility")
# Seeing everyone's private items goes with editing the whole inventory.
_SEE_PRIVATE = "inventory.items.update"


def item_relation(owner_id, responsible_id, member_id) -> str | None:
    """``"owner"``, ``"responsible"`` or None for *member_id* on an item."""
    if member_id is None:
        return None
    if owner_id == member_id:
        return "owner"
    if responsible_id == member_id:
        return "responsible"
    return None


def item_access(action: str):
    """``allow`` for ``permission_required``: lets the owner or the
    responsible person of the item in the route's ``item_id`` do *action*."""
    relations = ITEM_ACTIONS[action]

    def allow(member, item_id=None, **_):
        if item_id is None:
            return None
        row = db.session.execute(
            select(InventoryItem.owner_id, InventoryItem.responsible_id).where(
                InventoryItem.id == item_id
            )
        ).first()
        if row is None:
            return None
        relation = item_relation(row.owner_id, row.responsible_id, member.id)
        return relation if relation in relations else None

    return allow


def sees_private(member) -> bool:
    from hubra.api.permissions import member_has_permission

    return member_has_permission(member, _SEE_PRIVATE)


def can_see(item: InventoryItem, member) -> bool:
    """A private item is seen by its owner, its responsible person and
    whoever edits the whole inventory; a shared one by everyone who may read."""
    if item.visibility != "private":
        return True
    if item_relation(item.owner_id, item.responsible_id, member.id):
        return True
    return sees_private(member)


def _visible_to(viewer):
    """``can_see`` as a filter, for a viewer who doesn't see all private items."""
    return or_(
        InventoryItem.visibility != "private",
        InventoryItem.owner_id == viewer.id,
        InventoryItem.responsible_id == viewer.id,
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
    def get_visible(item_id: int, member) -> InventoryItem:
        """``get``, but a private item someone may not see is not found."""
        item = InventoryService.get(item_id)
        if not can_see(item, member):
            raise_error(404, "NOT_FOUND", f"Inventory item {item_id} not found")
        return item

    @staticmethod
    def check_owner_fields(item: InventoryItem, data: dict) -> None:
        """403 when the responsible person changes who owns or looks after
        the item or whether it is private. Sending the current value back
        (the edit form sends every field) is fine."""
        changed = [
            f for f in OWNER_FIELDS if f in data and data[f] != getattr(item, f)
        ]
        if changed:
            raise_error(
                403,
                "OWNER_ONLY",
                "Only the owner can change " + ", ".join(changed),
            )

    @staticmethod
    def update(item: InventoryItem, data: dict, actor_id: int) -> InventoryItem:
        """Update allowed fields on an inventory item."""
        # "checked_out" belongs to the checkout record: setting it by hand
        # left an item nobody had, and leaving it by hand an open checkout
        # that blocked the next one's check-in.
        status = data.get("status", item.status)
        if status != item.status and "checked_out" in (status, item.status):
            raise_error(
                409,
                "USE_CHECKOUT",
                "Use check out and check in to change whether an item is out",
            )
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
    def add_instruction(
        item: InventoryItem, member: Member, actor_id: int | None = None
    ) -> None:
        """Record a member being instructed on an item. Raises 409 if already."""
        if member.archived_at is not None:
            raise_error(404, "NOT_FOUND", f"Member {member.id} not found")
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
        log_audit(
            actor_id=actor_id,
            action="add_item_instruction",
            target_type="InventoryItem",
            target_id=item.id,
            target_label=f"{item.name}: {member.name}",
        )

    @staticmethod
    def remove_instruction(
        item_id: int, member_id: int, actor_id: int | None = None
    ) -> None:
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
        item = db.session.get(InventoryItem, item_id)
        member = db.session.get(Member, member_id)
        log_audit(
            actor_id=actor_id,
            action="remove_item_instruction",
            target_type="InventoryItem",
            target_id=item_id,
            target_label=f"{item.name if item else item_id}: "
            f"{member.name if member else member_id}",
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
        # Re-read under a row lock: two checkouts of one item must not both
        # see it available (Postgres; a no-op on SQLite).
        db.session.refresh(item, with_for_update=True)

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
    def list_overdue(viewer=None) -> list[InventoryCheckout]:
        """Return overdue checkouts (expected_return_at < now and not returned),
        with *viewer* only those of items they may see."""
        now = datetime.now(timezone.utc)
        query = select(InventoryCheckout)
        if viewer is not None and not sees_private(viewer):
            query = query.join(
                InventoryItem, InventoryItem.id == InventoryCheckout.item_id
            ).where(_visible_to(viewer))
        return db.session.scalars(
            query
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
        viewer=None,
    ) -> list[InventoryItem]:
        """Return inventory items with optional filters. With *viewer*, only
        the private items they may see (``can_see``)."""
        query = select(InventoryItem).options(*_LOAD_OPTS).order_by(InventoryItem.name)
        if viewer is not None and not sees_private(viewer):
            query = query.where(_visible_to(viewer))

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
