"""Federation view: an umbrella association sees its member clubs."""

from hubra.core.modules import Blueprint, Module, NavItem

module = Module(
    code="federation",
    name="Federation",
    description="For associations: member clubs with their member numbers and contacts, and events shared with them",
    default_enabled=False,
    depends_on=("members",),
    blueprints=(
        Blueprint(
            "hubra.api.federation.routes",
            "federation_bp",
            "/api/v1/app/federation",
        ),
    ),
    nav=(
        NavItem(
            "/app/federation",
            "shell.nav.federation",
            "building-community",
            order=14,
            perms=("federation.federation.read",),
        ),
    ),
)
