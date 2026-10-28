"""Applications blueprint — approve, decline, and manage membership applications."""

from __future__ import annotations

import re as _re

from flask import Blueprint, jsonify, request
from vollbuild.api.auth.helpers import get_current_member

from vollbuild.api.permissions import permission_required
from vollbuild.errors import api_error
from vollbuild.extensions import db, limiter
from vollbuild.core.schemas.application import ApplicationSchema
from vollbuild.core.schemas.member import MemberSchema
from vollbuild.api.applications.services import ApplicationService, ApplicationsService

applications_bp = Blueprint("applications_bp", __name__)

_application_schema = ApplicationSchema()
_applications_schema = ApplicationSchema(many=True)
_member_schema = MemberSchema()


# ── POST /applications (public — no auth required) ────────────────────────────


@applications_bp.post("/")
@limiter.limit("5 per minute")
def submit_application():
    body = request.get_json(silent=True) or {}
    first_name = (body.get("first_name") or "").strip()
    last_name = (body.get("last_name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    wants_tier_id = body.get("wants_tier_id")

    if not first_name or not last_name:
        return api_error("VALIDATION_ERROR", "First and last name are required", 400)
    if not email or not _re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return api_error("VALIDATION_ERROR", "A valid email is required", 400)

    app = ApplicationsService.submit(first_name, last_name, email, wants_tier_id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(_application_schema.dump(app)), 201


# ── GET /applications ─────────────────────────────────────────────────────────


@applications_bp.get("/")
@permission_required("applications", "read", "View applications")
def list_applications():
    return jsonify(_applications_schema.dump(ApplicationsService.list())), 200


# ── GET /applications/<id> ────────────────────────────────────────────────────


@applications_bp.get("/<int:application_id>")
@permission_required("applications", "read", "View applications")
def get_application(application_id: int):
    application = ApplicationService.get(application_id)
    return jsonify(_application_schema.dump(application)), 200


# ── POST /applications/<id>/approve ──────────────────────────────────────────


@applications_bp.post("/<int:application_id>/approve")
@permission_required("applications", "approve", "Approve applications")
def approve_application(application_id: int):
    member = ApplicationService.approve(application_id, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify(_member_schema.dump(member)), 201


# ── POST /applications/<id>/decline ──────────────────────────────────────────


@applications_bp.post("/<int:application_id>/decline")
@permission_required("applications", "decline", "Decline applications")
def decline_application(application_id: int):
    ApplicationService.decline(application_id, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204


# ── DELETE /applications/<id> ─────────────────────────────────────────────────


@applications_bp.delete("/<int:application_id>")
@permission_required("applications", "delete", "Delete applications")
def delete_application(application_id: int):
    ApplicationService.delete(application_id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204
