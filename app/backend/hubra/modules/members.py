"""Members: directory, membership applications and tiers."""

from hubra.core.modules import Blueprint, Module, NavItem

module = Module(
    code="members",
    name="Members",
    description="Member directory, profiles, applications and membership tiers",
    required=True,
    depends_on=("core",),
    blueprints=(
        Blueprint(
            "hubra.api.members.routes",
            "members_bp",
            "/api/v1/members",
            v2=(("/api/v2/tenants/members", "members_bp_v2"),),
        ),
        Blueprint(
            "hubra.api.applications.routes",
            "applications_bp",
            "/api/v1/applications",
            v2=(("/api/v2/tenants/applications", "applications_bp_v2"),),
        ),
        Blueprint(
            "hubra.api.tiers.routes",
            "tiers_bp",
            "/api/v1/tiers",
            v2=(("/api/v2/tenants/tiers", "tiers_bp_v2"),),
        ),
    ),
    nav=(
        NavItem(
            "/app/members",
            "shell.nav.members",
            "users",
            order=10,
            perms=(
                "members.members.read",
                "functions.functions.read",
                "applications.applications.read",
                "tiers.tiers.read",
            ),
        ),
    ),
    tables=(
        "members",
        "member_groups",
        "member_roles",
        "membership_tiers",
        "payment_plans",
        "applications",
    ),
)
