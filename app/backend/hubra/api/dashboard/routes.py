"""Dashboard blueprint — summary stats and growth data."""

from __future__ import annotations

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

from hubra.api.auth.helpers import get_current_member
from hubra.api.permissions import _get_member_permission_keys, member_is_admin

from hubra.core.schemas.event import ClubEventSchema
from hubra.core.schemas.post import PostSchema
from hubra.api.dashboard.services import DashboardService

dashboard_bp = Blueprint("dashboard_bp", __name__)

_event_schema = ClubEventSchema(many=True)
_post_schema = PostSchema(many=True)

# Club money totals; only for those who may see the finance overview.
_FINANCE_STATS = ("netMonth", "openInvoices", "openInvoicesAmount")


def _sees_finances(member) -> bool:
    return member_is_admin(member) or (
        "finance.overview.read" in _get_member_permission_keys(member)
    )


# ── GET /dashboard/summary ────────────────────────────────────────────────────


@dashboard_bp.get("/summary")
@jwt_required()
def get_summary():
    member = get_current_member()  # members of this club only
    result = DashboardService.get_summary()
    if not _sees_finances(member):
        # The open-invoice count and sum also feed the sidebar badge of
        # whoever works the invoices (finance.invoices.read).
        keep = (
            {"openInvoices", "openInvoicesAmount"}
            if "finance.invoices.read" in _get_member_permission_keys(member)
            else set()
        )
        for key in _FINANCE_STATS:
            if key not in keep:
                result["stats"][key] = None
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
