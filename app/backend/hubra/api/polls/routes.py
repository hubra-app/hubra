"""Polls blueprint — CRUD, voting, and closing."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from hubra.api.auth.helpers import get_current_member

from hubra.api.permissions import created_by, permission_required
from marshmallow import ValidationError
from hubra.core.errors import api_error
from hubra.core.extensions import db
from hubra.core.models.poll import Poll
from hubra.core.schemas.poll import (
    PollCreateSchema,
    PollSchema,
    PollUpdateSchema,
    VoteSchema,
)
from hubra.api.polls.services import PollService, PollsService, ProxyService

polls_bp = Blueprint("polls_bp", __name__)

# Whoever asked the question runs the poll: edits, reminds and closes it.
_own_poll = created_by(Poll, column="created_by_id", arg="poll_id")

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

    PollService.vote(
        poll, member_id, data["option_index"], on_behalf_of=data.get("on_behalf_of")
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    updated_poll = PollService.get(poll_id)
    return jsonify(_poll_schema.dump(updated_poll)), 200


# ── Proxy votes ──────────────────────────────────────────────────────────────


@polls_bp.get("/<int:poll_id>/proxy")
@permission_required("polls", "vote", "Vote on polls")
def get_proxy(poll_id: int):
    poll = PollService.get(poll_id)
    return jsonify(ProxyService.state(poll, get_current_member().id)), 200


@polls_bp.post("/<int:poll_id>/proxy")
@permission_required("polls", "vote", "Vote on polls")
def grant_proxy(poll_id: int):
    poll = PollService.get(poll_id)
    holder_id = (request.get_json(silent=True) or {}).get("holder_id")
    if not isinstance(holder_id, int) or isinstance(holder_id, bool):
        return api_error("VALIDATION_ERROR", "holder_id is required", 400)
    member_id = get_current_member().id
    ProxyService.grant(poll, member_id, holder_id)
    db.session.commit()
    return jsonify(ProxyService.state(poll, member_id)), 201


@polls_bp.delete("/<int:poll_id>/proxy")
@permission_required("polls", "vote", "Vote on polls")
def revoke_proxy(poll_id: int):
    poll = PollService.get(poll_id)
    member_id = get_current_member().id
    ProxyService.revoke(poll, member_id)
    db.session.commit()
    return jsonify(ProxyService.state(poll, member_id)), 200


# ── PATCH /polls/<id>/close ───────────────────────────────────────────────────


@polls_bp.patch("/<int:poll_id>/close")
@permission_required("polls", "close", "Close polls", allow=_own_poll)
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
@permission_required("polls", "update", "Update polls", allow=_own_poll)
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
@permission_required("polls", "update", "Update polls", allow=_own_poll)
def remind_poll(poll_id: int):
    sent = PollService.remind(poll_id, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify({"sent": sent}), 200
