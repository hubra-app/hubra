"""Members: directory, membership applications and tiers."""

from hubra.core.modules import Blueprint, Module, NavItem, Schedule

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
            "/api/v1/app/members",
        ),
        Blueprint(
            "hubra.api.applications.routes",
            "applications_bp",
            "/api/v1/app/applications",
        ),
        Blueprint(
            "hubra.api.tiers.routes",
            "tiers_bp",
            "/api/v1/app/tiers",
        ),
    ),
    nav=(
        NavItem(
            "/app/members",
            "shell.nav.members",
            "users",
            order=10,
            perms=("members.members.read",),
        ),
        NavItem(
            "/app/members/applications",
            "shell.nav.applications",
            "user-plus",
            order=12,
            perms=("applications.applications.read",),
        ),
        NavItem(
            "/app/members/tiers",
            "shell.nav.membershipTiers",
            "stairs",
            order=13,
            perms=("tiers.tiers.read",),
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
    tasks=("hubra.core.tasks.digest_tasks",),
    # The weekly digest goes out on Monday morning, club time; the hourly
    # run finds the hour in each club's time zone.
    schedule=(
        Schedule(
            "weekly-digest",
            "hubra.core.tasks.digest_tasks.send_weekly_digests_task",
            3600,
        ),
    ),
)
