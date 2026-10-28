"""Groups: organisational groups and member-joinable interest groups."""

from hubra.core.modules import Blueprint, Module, NavItem

module = Module(
    code="groups",
    name="Groups",
    description="Teams, committees and interest groups",
    default_enabled=True,
    depends_on=("members",),
    blueprints=(
        Blueprint(
            "hubra.api.groups.routes",
            "groups_bp",
            "/api/v1/groups",
        ),
    ),
    nav=(
        NavItem(
            "/app/groups",
            "shell.nav.groups",
            "box",
            order=20,
            perms=("groups.groups.read",),
        ),
    ),
    tables=("groups", "group_memberships"),
)
