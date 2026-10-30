"""Roles: role-based access control for club members."""

from hubra.core.modules import Blueprint, Module, NavItem

module = Module(
    code="roles",
    name="Roles & permissions",
    description="Roles and the permissions they grant",
    required=True,
    depends_on=("members",),
    blueprints=(
        Blueprint(
            "hubra.api.roles.routes",
            "roles_bp",
            "/api/v1/roles",
        ),
    ),
    nav=(
        NavItem(
            "/app/system",
            "shell.nav.permissions",
            "devices-cog",
            section="system",
            order=20,
            perms=(
                "roles.roles.create",
                "roles.roles.update",
                "roles.roles.set_permissions",
                "roles.roles.delete",
            ),
        ),
    ),
    # The permission catalog itself lives once in public (flask sync-permissions).
    tables=("roles", "role_permissions", "member_role_scopes"),
)
