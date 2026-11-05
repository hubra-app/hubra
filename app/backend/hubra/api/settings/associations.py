"""The member club's side of the federation view (hubra.core.services.federation).

``/api/v1/app/settings/associations``, for the club's admins:

* ``GET    /``            associations the club belongs to or is invited by
* ``POST   /<id>/accept`` join (``{"shareContacts": bool}``)
* ``PATCH  /<id>``        change ``shareContacts``
* ``DELETE /<id>``        decline the invitation or leave the association

A club decides itself: nothing is shared before it accepts, and the
contacts of its functions only when it says so.
"""

from __future__ import annotations

from flask import jsonify, request

from hubra.api.settings.routes import settings_bp
from hubra.core.auth.helpers import get_current_member
from hubra.core.errors import raise_error
from hubra.core.extensions import db
from hubra.core.permissions import require_admin
from hubra.core.services import federation
from hubra.core.tenant.context import current_tenant
from hubra.core.utils import log_audit


def _club():
    tenant = current_tenant()
    if tenant is None:
        raise_error(400, "NO_CLUB", "Open a club first")
    return tenant


def _share_contacts(required: bool) -> bool:
    data = request.get_json(silent=True)
    value = data.get("shareContacts") if isinstance(data, dict) else None
    if value is None and not required:
        return False
    if not isinstance(value, bool):
        raise_error(400, "VALIDATION_ERROR", "shareContacts must be true or false")
    return value


def _row(club, link_id: int) -> dict:
    rows = [a for a in federation.associations(club) if a["id"] == link_id]
    return rows[0] if rows else {"id": link_id}


def _audit(action: str, link) -> None:
    member = get_current_member()
    log_audit(
        member.id if member else None,
        action,
        "federation_link",
        link.id,
        str(link.federation_id),
    )


@settings_bp.get("/associations")
@require_admin
def list_associations():
    return jsonify({"associations": federation.associations(_club())}), 200


@settings_bp.post("/associations/<int:link_id>/accept")
@require_admin
def accept_association(link_id: int):
    club = _club()
    link = federation.link_of_club(club, link_id)
    share = _share_contacts(required=False)
    _audit("join_association", link)
    federation.accept(link, share)
    return jsonify(_row(club, link.id)), 200


@settings_bp.patch("/associations/<int:link_id>")
@require_admin
def update_association(link_id: int):
    club = _club()
    link = federation.link_of_club(club, link_id)
    share = _share_contacts(required=True)
    _audit(
        "share_contacts_with_association" if share else "stop_sharing_contacts", link
    )
    federation.set_share_contacts(link, share)
    return jsonify(_row(club, link.id)), 200


@settings_bp.delete("/associations/<int:link_id>")
@require_admin
def leave_association(link_id: int):
    link = federation.link_of_club(_club(), link_id)
    _audit("leave_association", link)
    federation.remove(link)
    db.session.commit()
    return "", 204
