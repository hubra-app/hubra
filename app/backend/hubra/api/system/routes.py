"""System diagnostic endpoints (admin-only)."""

from __future__ import annotations

from flask import Blueprint, jsonify

from hubra.api.permissions import require_admin
from hubra.api.system.services import SystemService

system_bp = Blueprint("system_bp", __name__)


@system_bp.get("/permissions")
@require_admin
def list_permissions():
    """Return a sorted list of all permission-gated endpoints."""
    return jsonify(SystemService.list_permissions()), 200
