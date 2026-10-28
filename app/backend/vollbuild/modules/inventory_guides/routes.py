"""Guides blueprint: /api/v1/guides/<item_id>.

The guide lives on the inventory item (``guide``, ``guide_url``) so it
stays with the item when the module is switched off and on again.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import or_, select

from vollbuild.api.auth.helpers import get_current_member
from vollbuild.api.inventory.services import InventoryService
from vollbuild.api.permissions import permission_required
from vollbuild.api.utils import log_audit
from vollbuild.core.errors import api_error
from vollbuild.core.extensions import db
from vollbuild.core.models.inventory import InventoryItem

guides_bp = Blueprint("guides_bp", __name__)

_MAX_GUIDE = 100_000


def _to_dict(item: InventoryItem) -> dict:
    return {
        "itemId": item.id,
        "itemName": item.name,
        "guide": item.guide or "",
        "guideUrl": item.guide_url,
        "instructionRequired": item.instruction_required,
    }


@guides_bp.get("/")
@permission_required("guides", "read", "Read guides")
def list_guides():
    items = db.session.scalars(
        select(InventoryItem)
        .where(InventoryItem.deleted_at.is_(None))
        .where(
            or_(InventoryItem.guide.isnot(None), InventoryItem.guide_url.isnot(None))
        )
        .order_by(InventoryItem.name)
    ).all()
    return jsonify([_to_dict(i) for i in items]), 200


@guides_bp.get("/<int:item_id>")
@permission_required("guides", "read", "Read guides")
def get_guide(item_id: int):
    return jsonify(_to_dict(InventoryService.get(item_id))), 200


@guides_bp.put("/<int:item_id>")
@permission_required("guides", "write", "Write guides")
def save_guide(item_id: int):
    body = request.get_json(silent=True) or {}
    guide = body.get("guide")
    url = body.get("guide_url")
    if guide is not None and not isinstance(guide, str):
        return api_error("VALIDATION_ERROR", "guide must be text", 400)
    if guide and len(guide) > _MAX_GUIDE:
        return api_error("VALIDATION_ERROR", "guide is too long", 400)
    if url:
        if not isinstance(url, str) or not url.startswith("https://"):
            return api_error(
                "VALIDATION_ERROR", "guide_url must start with https://", 400
            )
    item = InventoryService.get(item_id)
    if "guide" in body:
        item.guide = (guide or "").strip() or None
    if "guide_url" in body:
        item.guide_url = (url or "").strip() or None
    log_audit(
        get_current_member().id, "update_guide", "InventoryItem", item.id, item.name
    )
    db.session.commit()
    return jsonify(_to_dict(item)), 200
