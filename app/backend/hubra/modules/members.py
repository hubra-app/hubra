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
        ),
        Blueprint(
            "hubra.api.applications.routes",
            "applications_bp",
            "/api/v1/applications",
        ),
        Blueprint(
            "hubra.api.tiers.routes",
            "tiers_bp",
            "/api/v1/tiers",
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
