"""Bindings: connect club data to external APIs."""

from hubra.core.modules import Blueprint, Module, NavItem

module = Module(
    code="bindings",
    name="Bindings",
    description="Sync club data with external APIs",
    default_enabled=False,
    depends_on=("members",),
    blueprints=(
        Blueprint(
            "hubra.api.bindings.routes",
            "bindings_bp",
            "/api/v1/bindings",
            v2=(("/api/v2/tenants/bindings", "bindings_bp_v2"),),
        ),
    ),
    nav=(
        NavItem(
            "/app/operations/bindings",
            "shell.nav.bindings",
            "link",
            section="operations",
            order=30,
            perms=("bindings.bindings.read",),
        ),
    ),
    tables=("bindings",),
)
