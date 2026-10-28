"""Functions: club offices (president, treasurer, ...) and their holders."""

from vollbuild.core.modules import Blueprint, Module

module = Module(
    code="functions",
    name="Functions",
    description="Club offices and who holds them",
    default_enabled=True,
    depends_on=("members", "roles"),
    blueprints=(
        Blueprint(
            "vollbuild.api.functions.routes",
            "functions_bp",
            "/api/v1/functions",
            v2=(("/api/v2/tenants/functions", "functions_bp_v2"),),
        ),
    ),
    # Shown as a tab of the Members screen.
    tables=("functions", "function_holders"),
)
