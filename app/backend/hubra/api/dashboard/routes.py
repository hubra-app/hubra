"""Dashboard blueprint — summary stats and growth data."""

from __future__ import annotations

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

from hubra.api.auth.helpers import get_current_member

from hubra.core.schemas.event import ClubEventSchema
from hubra.core.schemas.post import PostSchema
from hubra.api.dashboard.services import DashboardService

dashboard_bp = Blueprint("dashboard_bp", __name__)

_event_schema = ClubEventSchema(many=True)
_post_schema = PostSchema(many=True)


# ── GET /dashboard/summary ────────────────────────────────────────────────────


@dashboard_bp.get("/summary")
@jwt_required()
def get_summary():
    get_current_member()  # members of this club only
    result = DashboardService.get_summary()
    upcoming_events = DashboardService.get_upcoming_events()
    recent_posts = DashboardService.get_recent_posts()

    return jsonify(
        {
            "stats": result["stats"],
            "growth": result["growth"],
            "upcomingEvents": _event_schema.dump(upcoming_events),
            "posts": _post_schema.dump(recent_posts),
        }
    ), 200
