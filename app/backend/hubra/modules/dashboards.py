"""Own dashboards: members put widgets together, privately or for the club."""

from hubra.core.modules import Blueprint, Module

module = Module(
    code="dashboards",
    name="Dashboards",
    description="Members build their own dashboards from widgets and may share them with the club",
    default_enabled=True,
    depends_on=("members",),
    blueprints=(
        Blueprint(
            "hubra.api.dashboards.routes",
            "dashboards_bp",
            "/api/v1/app/dashboards",
        ),
    ),
    tables=("dashboards",),
)
