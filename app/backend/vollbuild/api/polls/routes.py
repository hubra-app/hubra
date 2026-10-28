"""Polls blueprint — CRUD, voting, and closing."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from vollbuild.api.auth.helpers import get_current_member

from vollbuild.api.permissions import permission_required
from marshmallow import ValidationError
from vollbuild.errors import api_error
from vollbuild.extensions import db
from vollbuild.core.schemas.poll import (
    PollCreateSchema,
    PollSchema,
    PollUpdateSchema,
    VoteSchema,
)
from vollbuild.api.polls.services import PollService, PollsService

polls_bp = Blueprint("polls_bp", __name__)

_poll_schema = PollSchema()
_polls_schema = PollSchema(many=True)
_create_schema = PollCreateSchema()
_update_schema = PollUpdateSchema()
_vote_schema = VoteSchema()


# ── GET /polls ────────────────────────────────────────────────────────────────


@polls_bp.get("/")
@permission_required("polls", "read", "View polls")
def list_polls():
    return jsonify(_polls_schema.dump(PollsService.list())), 200


# ── GET /polls/<id> ───────────────────────────────────────────────────────────


@polls_bp.get("/<int:poll_id>")
@permission_required("polls", "read", "View polls")
def get_poll(poll_id: int):
    poll = PollService.get(poll_id)
    return jsonify(_poll_schema.dump(poll)), 200


# ── POST /polls ───────────────────────────────────────────────────────────────


@polls_bp.post("/")
@permission_required("polls", "create", "Create polls")
def create_poll():
    body = request.get_json(silent=True) or {}
    try:
        data = _create_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    poll = PollsService.create(data, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(_poll_schema.dump(poll)), 201


# ── POST /polls/<id>/vote ─────────────────────────────────────────────────────


@polls_bp.post("/<int:poll_id>/vote")
@permission_required("polls", "vote", "Vote on polls")
def cast_vote(poll_id: int):
    poll = PollService.get(poll_id)
    member_id = get_current_member().id

    body = request.get_json(silent=True) or {}
    try:
        data = _vote_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    PollService.vote(poll, member_id, data["option_index"])

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    updated_poll = PollService.get(poll_id)
    return jsonify(_poll_schema.dump(updated_poll)), 200


# ── PATCH /polls/<id>/close ───────────────────────────────────────────────────


@polls_bp.patch("/<int:poll_id>/close")
@permission_required("polls", "close", "Close polls")
def close_poll(poll_id: int):
    poll = PollService.get(poll_id)
    PollService.close(poll, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    db.session.refresh(poll)
    return jsonify(_poll_schema.dump(poll)), 200


# ── DELETE /polls/<id> ────────────────────────────────────────────────────────


@polls_bp.delete("/<int:poll_id>")
@permission_required("polls", "delete", "Delete polls")
def delete_poll(poll_id: int):
    PollService.delete(poll_id, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── PATCH /polls/<id> ──────────────────────────────────────────────────────────


@polls_bp.patch("/<int:poll_id>")
@permission_required("polls", "update", "Update polls")
def update_poll(poll_id: int):
    poll = PollService.get(poll_id)

    body = request.get_json(silent=True) or {}
    try:
        data = _update_schema.load(body)
    except ValidationError as exc:
        return api_error("VALIDATION_ERROR", str(exc.messages), 400)

    PollService.update(poll, data, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    db.session.refresh(poll)
    return jsonify(_poll_schema.dump(poll)), 200


# ── POST /polls/<id>/remind ────────────────────────────────────────────────────


@polls_bp.post("/<int:poll_id>/remind")
@permission_required("polls", "update", "Update polls")
def remind_poll(poll_id: int):
    sent = PollService.remind(poll_id, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify({"sent": sent}), 200
