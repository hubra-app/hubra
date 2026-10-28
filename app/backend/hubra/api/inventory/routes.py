"""Inventory blueprint — CRUD for InventoryItem + instruction tracking."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from hubra.api.auth.helpers import get_current_member
from marshmallow import ValidationError
from hubra.api.permissions import permission_required
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
from hubra.api.inventory.services import InventoryService, InventoryServiceItems

inventory_bp = Blueprint("inventory_bp", __name__)

_item_schema = InventoryItemSchema()
_items_schema = InventoryItemSchema(many=True)
_create_schema = InventoryItemCreateSchema()
_update_schema = InventoryItemUpdateSchema()


# ── GET /inventory ────────────────────────────────────────────────────────────


@inventory_bp.get("/")
@permission_required("items", "read", "View inventory")
def list_items():
    args = request.args
    items = InventoryServiceItems.list(
        category=args.get("category", "").strip(),
        status=args.get("status", "").strip(),
        visibility=args.get("visibility", "").strip(),
    )
    return jsonify(_items_schema.dump(items)), 200


# ── GET /inventory/<id> ───────────────────────────────────────────────────────


@inventory_bp.get("/<int:item_id>")
@permission_required("items", "read", "View inventory")
def get_item(item_id: int):
    item = InventoryService.get(item_id)
    return jsonify(_item_schema.dump(item)), 200


# ── POST /inventory ───────────────────────────────────────────────────────────


@inventory_bp.post("/")
@permission_required("items", "create", "Create inventory items")
def create_item():
    body = request.get_json(silent=True) or {}
    try:
        data = _create_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    item = InventoryServiceItems.create(data, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(_item_schema.dump(item)), 201


# ── PATCH /inventory/<id> ─────────────────────────────────────────────────────


@inventory_bp.patch("/<int:item_id>")
@permission_required("items", "update", "Update inventory items")
def update_item(item_id: int):
    item = InventoryService.get(item_id)

    body = request.get_json(silent=True) or {}
    try:
        data = _update_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

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
@permission_required("items", "delete", "Delete inventory items")
def delete_item(item_id: int):
    InventoryService.delete(item_id, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── POST /inventory/<id>/instructions/<member_id> ─────────────────────────────


@inventory_bp.post("/<int:item_id>/instructions/<int:member_id>")
@permission_required("items", "manage_instructions", "Manage item instructions")
def add_instruction(item_id: int, member_id: int):
    item = InventoryService.get(item_id)

    member = db.session.get(Member, member_id)
    if member is None:
        raise_error(404, "NOT_FOUND", f"Member {member_id} not found")
        return

    InventoryService.add_instruction(item, member)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── POST /inventory/<id>/checkout ────────────────────────────────────────────


@inventory_bp.post("/<int:item_id>/checkout")
@permission_required("items", "checkout", "Check out inventory items")
def checkout_item(item_id: int):
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
@permission_required("items", "checkin", "Check in inventory items")
def checkin_item(item_id: int):
    body = request.get_json(silent=True) or {}
    condition_notes = body.get("condition_notes")

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
    overdues = InventoryService.list_overdue()
    return jsonify(InventoryCheckoutSchema(many=True).dump(overdues)), 200


# ── DELETE /inventory/<id>/instructions/<member_id> ───────────────────────────


@inventory_bp.delete("/<int:item_id>/instructions/<int:member_id>")
@permission_required("items", "manage_instructions", "Manage item instructions")
def remove_instruction(item_id: int, member_id: int):
    InventoryService.remove_instruction(item_id, member_id)

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
    item = InventoryService.get(item_id)

    from hubra.core.models.member import Member as MemberModel

    member = db.session.get(MemberModel, member_id)
    if member is None:
        raise_error(404, "NOT_FOUND", f"Member {member_id} not found")
        return

    InventoryService.add_instruction(item, member)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204
