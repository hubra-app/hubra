"""Functions: club offices (president, treasurer, ...) and their holders."""

from hubra.core.modules import Blueprint, Module, NavItem

module = Module(
    code="functions",
    name="Functions",
    description="Club offices and who holds them",
    default_enabled=True,
    depends_on=("members", "roles"),
    blueprints=(
        Blueprint(
            "hubra.api.functions.routes",
            "functions_bp",
            "/api/v1/functions",
        ),
    ),
    nav=(
        NavItem(
            "/app/members/functions",
            "shell.nav.functions",
            "id-badge",
            order=11,
            perms=("functions.functions.read",),
            parent="/app/members",
        ),
    ),
    tables=("functions", "function_holders"),
)
