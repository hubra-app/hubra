"""The club's permission catalogue, for its role editor (club admins).

manage shows the same list to platform staff at
``/api/v1/manager/platform/permissions``.
"""

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
