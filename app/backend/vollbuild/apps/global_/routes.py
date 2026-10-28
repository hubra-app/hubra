"""Global plane v2 blueprint registration.

Registers auth, account, i18n, health, version, and system endpoints
under /api/v2/global/* alongside the existing v1 routes.
"""

from __future__ import annotations

from flask import Flask

from vollbuild.apps import _register_v2_blueprints

_V2_SPECS = [
    ("vollbuild.api.auth.routes", "auth_bp", "/api/v2/global/auth", "auth_bp_v2"),
    (
        "vollbuild.api.auth.routes",
        "account_bp",
        "/api/v2/global/account",
        "account_bp_v2",
    ),
    ("vollbuild.api.i18n.routes", "i18n_bp", "/api/v2/global/i18n", "i18n_bp_v2"),
    ("vollbuild.api.health.routes", "health_bp", "/api/v2/global", "health_bp_v2"),
    ("vollbuild.api.version.routes", "version_bp", "/api/v2/global", "version_bp_v2"),
    (
        "vollbuild.api.system.routes",
        "system_bp",
        "/api/v2/global/system",
        "system_bp_v2",
    ),
]


def register_global_v2(app: Flask) -> None:
    """Register v2 global-plane blueprints."""
    _register_v2_blueprints(app, _V2_SPECS)
