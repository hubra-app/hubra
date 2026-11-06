"""The association's side of the federation view (hubra.core.services.federation).

``/api/v1/app/federation``:

* ``GET    /clubs``         member clubs and open invitations, with numbers
* ``POST   /clubs``         invite a club by its address (``{"slug": ...}``)
* ``DELETE /clubs/<id>``    withdraw an invitation or remove a member club

The member club accepts in its own settings (``/app/settings/associations``).
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from hubra.core.auth.helpers import get_current_member
from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.permissions import permission_required
from hubra.core.services import federation
from hubra.core.tenant.context import current_tenant
from hubra.core.utils import log_audit

federation_bp = Blueprint("federation_bp", __name__)


def _tenant():
    tenant = current_tenant()
    if tenant is None:
        raise_error(400, "NO_CLUB", "Open a club first")
    return tenant


@federation_bp.get("/clubs")
@permission_required("federation", "read", "See the association's member clubs")
def list_clubs():
    get_current_member()
    return jsonify({"clubs": federation.member_clubs(_tenant())}), 200


@federation_bp.post("/clubs")
@permission_required("federation", "manage", "Invite and remove member clubs")
def invite_club():
    member = get_current_member()
    data = request.get_json(silent=True)
    slug = data.get("slug") if isinstance(data, dict) else None
    if not isinstance(slug, str):
        raise_error(400, "VALIDATION_ERROR", "Give the club's address")
    tenant = _tenant()
    link = federation.invite(tenant, slug, by=tenant.name)
    log_audit(
        member.id if member else None,
        "invite_member_club",
        "federation_link",
        link.id,
        slug.strip().lower(),
    )
    db.session.commit()
    rows = [c for c in federation.member_clubs(tenant) if c["id"] == link.id]
    return jsonify(rows[0] if rows else {"id": link.id}), 201


@federation_bp.delete("/clubs/<int:link_id>")
@permission_required("federation", "manage", "Invite and remove member clubs")
def remove_club(link_id: int):
    member = get_current_member()
    link = federation.link_of_federation(_tenant(), link_id)
    log_audit(
        member.id if member else None,
        "remove_member_club",
        "federation_link",
        link.id,
        str(link.club_id),
    )
    federation.remove(link)
    return "", 204
