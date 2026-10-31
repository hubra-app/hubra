"""Inventory blueprint — CRUD for InventoryItem + instruction tracking."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request
from hubra.api.auth.helpers import get_current_member
from marshmallow import ValidationError
from hubra.api.permissions import member_has_permission, permission_required
from hubra.core.errors import api_error, raise_error
from hubra.core.extensions import db
from hubra.core.models.member import Member
from hubra.core.schemas.inventory import (
    InventoryItemCreateSchema,
    InventoryItemSchema,
    InventoryItemUpdateSchema,
    InventoryCheckoutSchema,
    CheckoutCreateSchema,
)
from hubra.api.inventory.services import (
    InventoryService,
    InventoryServiceItems,
    item_access,
)

inventory_bp = Blueprint("inventory_bp", __name__)

_item_schema = InventoryItemSchema()
_items_schema = InventoryItemSchema(many=True)
_create_schema = InventoryItemCreateSchema()
_update_schema = InventoryItemUpdateSchema()

# Object-level rights: the owner or responsible person of an item passes
# these routes without the club-wide right (see services.ITEM_ACTIONS).
_CREATE_OWN = "inventory.items.create_own"


def _by_object() -> bool:
    """True when the request passed as the item's owner or responsible
    person rather than through a role."""
    return g.get("permission_scope") == "object"


def _may_create_own(member, **_):
    return "own" if member_has_permission(member, _CREATE_OWN) else None


# ── GET /inventory ────────────────────────────────────────────────────────────


@inventory_bp.get("/")
@permission_required("items", "read", "View inventory")
def list_items():
    args = request.args
    items = InventoryServiceItems.list(
        category=args.get("category", "").strip(),
        status=args.get("status", "").strip(),
        visibility=args.get("visibility", "").strip(),
        viewer=get_current_member(),
    )
    return jsonify(_items_schema.dump(items)), 200


# ── GET /inventory/<id> ───────────────────────────────────────────────────────


@inventory_bp.get("/<int:item_id>")
@permission_required("items", "read", "View inventory", allow=item_access("read"))
def get_item(item_id: int):
    item = InventoryService.get_visible(item_id, get_current_member())
    return jsonify(_item_schema.dump(item)), 200


# ── POST /inventory ───────────────────────────────────────────────────────────


@inventory_bp.post("/")
@permission_required(
    "items", "create", "Create inventory items", allow=_may_create_own
)
def create_item():
    body = request.get_json(silent=True) or {}
    try:
        data = _create_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)
    if _by_object():
        # With only "add own items", the item is always the member's own.
        data["owner_id"] = get_current_member().id

    item = InventoryServiceItems.create(data, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(_item_schema.dump(item)), 201


# ── PATCH /inventory/<id> ─────────────────────────────────────────────────────


@inventory_bp.patch("/<int:item_id>")
@permission_required(
    "items", "update", "Update inventory items", allow=item_access("update")
)
def update_item(item_id: int):
    item = InventoryService.get_visible(item_id, get_current_member())

    body = request.get_json(silent=True) or {}
    try:
        data = _update_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)
    if _by_object() and g.object_access != "owner":
        InventoryService.check_owner_fields(item, data)

    InventoryService.update(item, data, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    db.session.refresh(item)
    item = InventoryService.get(item.id)
    return jsonify(_item_schema.dump(item)), 200


# ── DELETE /inventory/<id> ────────────────────────────────────────────────────


@inventory_bp.delete("/<int:item_id>")
@permission_required(
    "items", "delete", "Delete inventory items", allow=item_access("delete")
)
def delete_item(item_id: int):
    InventoryService.get_visible(item_id, get_current_member())
    InventoryService.delete(item_id, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── POST /inventory/<id>/instructions/<member_id> ─────────────────────────────


@inventory_bp.post("/<int:item_id>/instructions/<int:member_id>")
@permission_required(
    "items",
    "manage_instructions",
    "Manage item instructions",
    allow=item_access("manage_instructions"),
)
def add_instruction(item_id: int, member_id: int):
    item = InventoryService.get_visible(item_id, get_current_member())

    member = db.session.get(Member, member_id)
    if member is None:
        raise_error(404, "NOT_FOUND", f"Member {member_id} not found")
        return

    InventoryService.add_instruction(item, member, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── POST /inventory/<id>/checkout ────────────────────────────────────────────


@inventory_bp.post("/<int:item_id>/checkout")
@permission_required(
    "items", "checkout", "Check out inventory items", allow=item_access("checkout")
)
def checkout_item(item_id: int):
    InventoryService.get_visible(item_id, get_current_member())
    body = request.get_json(silent=True) or {}
    try:
        data = CheckoutCreateSchema().load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    checkout = InventoryService.checkout(
        item_id=item_id,
        member_id=data["member_id"],
        expected_return_at=data.get("expected_return_at"),
        condition_notes=data.get("condition_notes"),
        actor_id=get_current_member().id,
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(InventoryCheckoutSchema().dump(checkout)), 201


# ── POST /inventory/<id>/checkin ─────────────────────────────────────────────


@inventory_bp.post("/<int:item_id>/checkin")
@permission_required(
    "items", "checkin", "Check in inventory items", allow=item_access("checkin")
)
def checkin_item(item_id: int):
    InventoryService.get_visible(item_id, get_current_member())
    body = request.get_json(silent=True) or {}
    condition_notes = body.get("condition_notes")
    if condition_notes is not None and not isinstance(condition_notes, str):
        return api_error("VALIDATION_ERROR", "condition_notes must be text", 400)

    checkout = InventoryService.checkin(
        item_id=item_id,
        condition_notes=condition_notes,
        actor_id=get_current_member().id,
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(InventoryCheckoutSchema().dump(checkout)), 200


# ── GET /inventory/overdue ───────────────────────────────────────────────────


@inventory_bp.get("/overdue")
@permission_required("items", "read", "View inventory")
def list_overdue():
    overdues = InventoryService.list_overdue(viewer=get_current_member())
    return jsonify(InventoryCheckoutSchema(many=True).dump(overdues)), 200


# ── DELETE /inventory/<id>/instructions/<member_id> ───────────────────────────


@inventory_bp.delete("/<int:item_id>/instructions/<int:member_id>")
@permission_required(
    "items",
    "manage_instructions",
    "Manage item instructions",
    allow=item_access("manage_instructions"),
)
def remove_instruction(item_id: int, member_id: int):
    InventoryService.get_visible(item_id, get_current_member())
    InventoryService.remove_instruction(item_id, member_id, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── POST /inventory/<id>/instructions/self ────────────────────────────────────


@inventory_bp.post("/<int:item_id>/instructions/self")
@permission_required("items", "instruct_self", "Add self-instruction for items")
def add_self_instruction(item_id: int):
    member_id = get_current_member().id
    item = InventoryService.get_visible(item_id, get_current_member())

    from hubra.core.models.member import Member as MemberModel

    member = db.session.get(MemberModel, member_id)
    if member is None:
        raise_error(404, "NOT_FOUND", f"Member {member_id} not found")
        return

    InventoryService.add_instruction(item, member, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204
