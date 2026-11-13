"""The club calendar: events, bookings, fixtures and duties side by side.

Each module offers its items through ``<module>.calendar.items``
(hubra.core.contracts.calendar); this asks every module the member may see.
"""

from __future__ import annotations

from datetime import date

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from hubra.core.auth.helpers import get_current_member
from hubra.core.contracts import calendar
from hubra.core.errors import api_error

calendar_bp = Blueprint("calendar_bp", __name__)


@calendar_bp.get("/")
@jwt_required()
def club_calendar():
    """``?start=YYYY-MM-DD&end=YYYY-MM-DD`` (both included, at most
    ``MAX_DAYS`` apart) → ``{items, sources, failed}``."""
    get_current_member()  # members of this club only
    try:
        start = date.fromisoformat(request.args.get("start", ""))
        end = date.fromisoformat(request.args.get("end", ""))
    except ValueError:
        return api_error("VALIDATION_ERROR", "start and end as YYYY-MM-DD", 400)
    if end < start or (end - start).days > calendar.MAX_DAYS:
        return api_error(
            "VALIDATION_ERROR",
            f"end after start, at most {calendar.MAX_DAYS} days apart",
            400,
        )
    return jsonify(calendar.items(start, end)), 200
