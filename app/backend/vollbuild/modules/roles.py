"""Roles: role-based access control for club members."""

from vollbuild.core.modules import Blueprint, Module, NavItem

module = Module(
    code="roles",
    name="Roles & permissions",
    description="Roles and the permissions they grant",
    required=True,
    depends_on=("members",),
    blueprints=(
        Blueprint(
            "vollbuild.api.roles.routes",
            "roles_bp",
            "/api/v1/roles",
            v2=(("/api/v2/tenants/roles", "roles_bp_v2"),),
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
    tables=("roles", "permissions", "role_permissions"),
)
