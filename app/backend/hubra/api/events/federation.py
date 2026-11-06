"""Events an association shares with its member clubs (docs/federation.md).

``GET /api/v1/app/events/from-associations``: the upcoming events of every
association this club has joined that are marked for member clubs.
"""

from __future__ import annotations

from flask import jsonify
from flask_jwt_extended import jwt_required

from hubra.api.events.routes import events_bp
from hubra.core.auth.helpers import get_current_member
from hubra.core.services import federation
from hubra.core.tenant.context import current_tenant


@events_bp.get("/from-associations")
@jwt_required()
def association_events():
    get_current_member()  # members of this club only
    club = current_tenant()
    events = federation.shared_events(club) if club is not None else []
    return jsonify({"events": events}), 200
