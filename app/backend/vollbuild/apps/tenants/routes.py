"""Tenant (COS) plane v2 blueprint registration.

Registers all tenant-scoped endpoints under /api/v2/tenants/* alongside
the existing v1 routes. The tenant slug is extracted from the path by
the tenant middleware before the blueprint sees the request.
"""

from __future__ import annotations

from flask import Flask

from vollbuild.apps import _register_v2_blueprints

_V2_SPECS = [
    (
        "vollbuild.api.members.routes",
        "members_bp",
        "/api/v2/tenants/members",
        "members_bp_v2",
    ),
    (
        "vollbuild.api.applications.routes",
        "applications_bp",
        "/api/v2/tenants/applications",
        "applications_bp_v2",
    ),
    (
        "vollbuild.api.groups.routes",
        "groups_bp",
        "/api/v2/tenants/groups",
        "groups_bp_v2",
    ),
    (
        "vollbuild.api.functions.routes",
        "functions_bp",
        "/api/v2/tenants/functions",
        "functions_bp_v2",
    ),
    (
        "vollbuild.api.events.routes",
        "events_bp",
        "/api/v2/tenants/events",
        "events_bp_v2",
    ),
    (
        "vollbuild.api.polls.routes",
        "polls_bp",
        "/api/v2/tenants/polls",
        "polls_bp_v2",
    ),
    (
        "vollbuild.api.posts.routes",
        "posts_bp",
        "/api/v2/tenants/posts",
        "posts_bp_v2",
    ),
    (
        "vollbuild.api.finance.routes",
        "finance_bp",
        "/api/v2/tenants/finance",
        "finance_bp_v2",
    ),
    (
        "vollbuild.api.mail.routes",
        "mail_bp",
        "/api/v2/tenants/mail",
        "mail_bp_v2",
    ),
    (
        "vollbuild.api.settings.routes",
        "settings_bp",
        "/api/v2/tenants/settings",
        "settings_bp_v2_tenant",
    ),
    (
        "vollbuild.api.roles.routes",
        "roles_bp",
        "/api/v2/tenants/roles",
        "roles_bp_v2",
    ),
    (
        "vollbuild.api.tiers.routes",
        "tiers_bp",
        "/api/v2/tenants/tiers",
        "tiers_bp_v2",
    ),
    (
        "vollbuild.api.audit.routes",
        "audit_bp",
        "/api/v2/tenants/audit",
        "audit_bp_v2",
    ),
    (
        "vollbuild.api.inventory.routes",
        "inventory_bp",
        "/api/v2/tenants/inventory",
        "inventory_bp_v2",
    ),
    (
        "vollbuild.api.codes.routes",
        "codes_bp",
        "/api/v2/tenants/codes",
        "codes_bp_v2",
    ),
    (
        "vollbuild.api.bindings.routes",
        "bindings_bp",
        "/api/v2/tenants/bindings",
        "bindings_bp_v2",
    ),
    (
        "vollbuild.api.dashboard.routes",
        "dashboard_bp",
        "/api/v2/tenants/dashboard",
        "dashboard_bp_v2",
    ),
    (
        "vollbuild.api.notifications.routes",
        "notifications_bp",
        "/api/v2/tenants/notifications",
        "notifications_bp_v2",
    ),
    (
        "vollbuild.api.backups.routes",
        "backups_bp",
        "/api/v2/tenants/backups",
        "backups_bp_v2",
    ),
]


def register_tenants_v2(app: Flask) -> None:
    """Register v2 tenant-plane blueprints."""
    _register_v2_blueprints(app, _V2_SPECS)
