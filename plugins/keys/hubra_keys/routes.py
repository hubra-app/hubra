"""Keys blueprint: /api/v1/keys."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from hubra.api.auth.helpers import get_current_member
from hubra.api.permissions import permission_required, require_member
from hubra.core.errors import api_error
from hubra.core.extensions import db

from .services import KeyService, key_to_dict

keys_bp = Blueprint("keys_bp", __name__)


def _body() -> dict:
    return request.get_json(silent=True) or {}


def _done(key, status=200):
    db.session.commit()
    return jsonify(key_to_dict(key, with_history=True)), status


@keys_bp.get("/")
@permission_required("keys", "read", "View keys")
def list_keys():
    holder = request.args.get("holder_id", type=int)
    keys = KeyService.list(status=request.args.get("status"), holder_id=holder)
    return jsonify([key_to_dict(k) for k in keys]), 200


@keys_bp.get("/mine")
@require_member
def my_keys():
    """Keys the signed-in member holds; no permission needed."""
    keys = KeyService.list(holder_id=get_current_member().id)
    # The holder's view: no manager notes, no code link, no retired keys.
    hidden = ("notes", "codeId", "holderId", "holderName")
    return (
        jsonify(
            [
                {k: v for k, v in key_to_dict(key).items() if k not in hidden}
                for key in keys
                if key.status != "retired"
            ]
        ),
        200,
    )


@keys_bp.get("/<int:key_id>")
@permission_required("keys", "read", "View keys")
def get_key(key_id: int):
    return jsonify(key_to_dict(KeyService.get(key_id), with_history=True)), 200


@keys_bp.post("/")
@permission_required("keys", "manage", "Manage keys")
def create_key():
    return _done(KeyService.create(_body(), get_current_member().id), 201)


@keys_bp.patch("/<int:key_id>")
@permission_required("keys", "manage", "Manage keys")
def update_key(key_id: int):
    return _done(KeyService.update(key_id, _body(), get_current_member().id))


@keys_bp.delete("/<int:key_id>")
@permission_required("keys", "manage", "Manage keys")
def delete_key(key_id: int):
    KeyService.delete(key_id, get_current_member().id)
    db.session.commit()
    return "", 204


@keys_bp.post("/<int:key_id>/issue")
@permission_required("keys", "manage", "Manage keys")
def issue_key(key_id: int):
    body = _body()
    if not isinstance(body.get("member_id"), int):
        return api_error("VALIDATION_ERROR", "member_id is required", 400)
    key = KeyService.issue(
        key_id, body["member_id"], get_current_member().id, body.get("note")
    )
    return _done(key)


@keys_bp.post("/<int:key_id>/return")
@permission_required("keys", "manage", "Manage keys")
def return_key(key_id: int):
    return _done(
        KeyService.take_back(key_id, get_current_member().id, _body().get("note"))
    )


@keys_bp.post("/<int:key_id>/lost")
@permission_required("keys", "manage", "Manage keys")
def lose_key(key_id: int):
    return _done(
        KeyService.mark_lost(key_id, get_current_member().id, _body().get("note"))
    )


@keys_bp.post("/<int:key_id>/found")
@permission_required("keys", "manage", "Manage keys")
def find_key(key_id: int):
    return _done(
        KeyService.mark_found(key_id, get_current_member().id, _body().get("note"))
    )


@keys_bp.post("/<int:key_id>/retire")
@permission_required("keys", "manage", "Manage keys")
def retire_key(key_id: int):
    return _done(
        KeyService.retire(key_id, get_current_member().id, _body().get("note"))
    )
