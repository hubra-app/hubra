"""Data protection self-service: /members/me/privacy and the board's view
of a member's consent history. Rules live in hubra.core.services.privacy."""

from __future__ import annotations

import json

from flask import Response, jsonify, request
from flask_jwt_extended import jwt_required

from hubra.api.members.routes import members_bp
from hubra.api.members.services import MemberService
from hubra.core.auth.helpers import get_current_member
from hubra.core.errors import raise_error
from hubra.core.extensions import db, limiter
from hubra.core.permissions import permission_required, refuse_during_impersonation
from hubra.core.services import privacy


def _tenant():
    from hubra.core.tenant.context import current_tenant

    tenant = current_tenant()
    if tenant is None:
        raise_error(400, "NO_CLUB", "Open a club first")
    return tenant


@members_bp.get("/me/privacy")
@jwt_required()
def get_my_privacy():
    """Consents, an open deletion request and the club's retention rule."""
    return jsonify(privacy.overview(_tenant(), get_current_member())), 200


@members_bp.put("/me/privacy")
@jwt_required()
def set_my_privacy():
    body = request.get_json(silent=True) or {}
    if "photo_consent" not in body or not isinstance(body["photo_consent"], bool):
        raise_error(422, "VALIDATION_ERROR", "photo_consent must be true or false")
    refuse_during_impersonation()
    member = get_current_member()
    privacy.set_photo_consent(member, body["photo_consent"], member.id)
    db.session.commit()
    return jsonify(privacy.overview(_tenant(), member)), 200


@members_bp.get("/me/privacy/export")
@jwt_required()
@limiter.limit("5 per hour")
def export_my_data():
    """Everything the club holds about me, as a JSON download."""
    refuse_during_impersonation()
    tenant = _tenant()
    data = privacy.export_own(tenant, get_current_member())
    db.session.commit()
    name = f"hubra-{tenant.slug}-my-data.json"
    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Cache-Control": "no-store",
        },
    )


@members_bp.post("/me/privacy/deletion")
@jwt_required()
@limiter.limit("5 per hour")
def request_my_deletion():
    """Ask for my club data to be deleted (handled by the platform)."""
    refuse_during_impersonation()
    body = request.get_json(silent=True) or {}
    note = body.get("note") or ""
    if not isinstance(note, str):
        raise_error(422, "VALIDATION_ERROR", "note must be text")
    tenant = _tenant()
    member = get_current_member()
    privacy.request_deletion(tenant, member, note.strip())
    db.session.commit()
    return jsonify(privacy.overview(tenant, member)), 201


@members_bp.get("/<int:member_id>/consents")
@permission_required("members", "read", "View members")
def get_member_consents(member_id: int):
    """A member's consents now and every change, for the board."""
    member = MemberService.get(member_id)
    if member is None:
        raise_error(404, "NOT_FOUND", f"Member {member_id} not found")
    return jsonify(
        {
            "photo_consent": member.photo_consent,
            "directory_shared": list(member.directory_shared or []),
            "log": privacy.consent_log(member.id),
        }
    ), 200
