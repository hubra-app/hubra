"""Manager plane v2 blueprint registration.

Registers admin, tenant_admin, features, and settings endpoints
under /api/v2/manager/* alongside the existing v1 routes.
"""

from __future__ import annotations

from flask import Flask

from vollbuild.apps import _register_v2_blueprints

_V2_SPECS = [
    (
        "vollbuild.api.admin.routes",
        "admin_bp",
        "/api/v2/manager/tenants",
        "admin_bp_v2",
    ),
    (
        "vollbuild.api.tenant.routes",
        "tenant_admin_bp",
        "/api/v2/manager/tenants",
        "tenant_admin_bp_v2",
    ),
    (
        "vollbuild.api.features.routes",
        "features_bp",
        "/api/v2/manager/features",
        "features_bp_v2",
    ),
    (
        "vollbuild.api.settings.routes",
        "settings_bp",
        "/api/v2/manager/settings",
        "settings_bp_v2_manager",
    ),
]


def register_manager_v2(app: Flask) -> None:
    """Register v2 manager-plane blueprints."""
    _register_v2_blueprints(app, _V2_SPECS)
