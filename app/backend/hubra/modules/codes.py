"""Codes: encrypted storage for door codes, passcodes and similar secrets."""

from hubra.core.modules import Blueprint, Module, NavItem

module = Module(
    code="codes",
    name="Codes",
    description="Encrypted door codes and passcodes",
    default_enabled=False,
    depends_on=("members",),
    blueprints=(
        Blueprint(
            "hubra.api.codes.routes",
            "codes_bp",
            "/api/v1/codes",
        ),
    ),
    nav=(
        NavItem(
            "/app/operations/codes",
            "shell.nav.codes",
            "lock",
            section="operations",
            order=20,
            perms=("codes.codes.read",),
        ),
    ),
    tables=("codes",),
)
