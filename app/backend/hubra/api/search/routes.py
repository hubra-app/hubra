"""The club search: one box for members, events, posts, invoices and what
plugins offer (``<module>.search``, hubra.core.contracts.search)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from hubra.core.auth.helpers import get_current_member
from hubra.core.contracts import search
from hubra.core.errors import api_error
from hubra.core.extensions import limiter

search_bp = Blueprint("search_bp", __name__)


@search_bp.get("/")
@jwt_required()
@limiter.limit("60 per minute")
def club_search():
    """``?q=`` (2 to 100 characters) → ``{hits, failed}``: up to five hits
    per module, each with its ``source``."""
    get_current_member()  # members of this club only
    q = (request.args.get("q") or "").strip()
    if not 2 <= len(q) <= 100:
        return api_error("VALIDATION_ERROR", "q: 2 to 100 characters", 400)
    return jsonify(search.search(q)), 200
