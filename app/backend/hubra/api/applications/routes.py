"""Applications blueprint — approve, decline, and manage membership applications."""

from __future__ import annotations


from flask import Blueprint, jsonify, request
from hubra.core.auth.helpers import get_current_member

from hubra.core.errors import api_error
from hubra.core.permissions import permission_required
from hubra.core.extensions import db
from hubra.core.schemas.application import ApplicationSchema
from hubra.core.schemas.member import MemberSchema
from hubra.api.applications.services import ApplicationService, ApplicationsService

applications_bp = Blueprint("applications_bp", __name__)

_application_schema = ApplicationSchema()
_applications_schema = ApplicationSchema(many=True)
_member_schema = MemberSchema()


# People ask to join on the SSO portal (POST /system/clubs/<slug>/join),
# signed in with a verified address; there is no anonymous form any more.


# ── GET /applications ─────────────────────────────────────────────────────────


@applications_bp.get("/")
@permission_required("applications", "read", "View applications")
def list_applications():
    return jsonify(_applications_schema.dump(ApplicationsService.list())), 200


# ── Posters: a QR code to the join or trial page, with a source tag ─────────


@applications_bp.get("/poster")
@permission_required("applications", "read", "View applications")
def poster():
    """The link and QR code for a join or trial poster:
    ``?kind=join|trial&source=<tag>`` gives ``{url, qrSvg, source, club}``."""
    from urllib.parse import quote

    from hubra.core.auth.mfa import qr_svg
    from hubra.core.services import signup_source
    from hubra.core.services.email import _get_sso_base_url
    from hubra.core.tenant.context import current_tenant

    kind = request.args.get("kind", "join")
    if kind not in signup_source.KINDS:
        return api_error("VALIDATION_ERROR", "kind is join or trial", 400)
    tenant = current_tenant()
    if tenant is None:
        return api_error("NO_TENANT", "No club", 400)
    source = signup_source.clean(request.args.get("source"))
    url = f"{_get_sso_base_url()}/clubs/{quote(tenant.slug)}"
    if kind == "trial":
        url += "/trial"
    if source:
        url += f"?src={source}"
    return jsonify(
        {
            "url": url,
            "qrSvg": qr_svg(url),
            "source": source,
            "club": {"name": tenant.name, "slug": tenant.slug},
        }
    ), 200


@applications_bp.get("/sources")
@permission_required("applications", "read", "View applications")
def sources():
    """Requests to join and trial bookings per poster tag, last 12 months."""
    from hubra.core.services import signup_source

    return jsonify(signup_source.summary()), 200


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

    if member is None:
        # No account yet: the applicant got an invite to sign up and accept.
        return jsonify({"invited": True}), 202
    ApplicationService.queue_mailbox(member)
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
    ApplicationService.delete(application_id, get_current_member().id)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return "", 204
