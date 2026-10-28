"""Inventory: tools, machines, items and materials, checkouts and inductions."""

from vollbuild.core.modules import Blueprint, Module, NavItem, SettingField

module = Module(
    code="inventory",
    name="Inventory",
    description="Tools, machines and materials, checkouts and inductions",
    default_enabled=False,
    depends_on=("members",),
    blueprints=(
        Blueprint(
            "vollbuild.api.inventory.routes",
            "inventory_bp",
            "/api/v1/inventory",
            v2=(("/api/v2/tenants/inventory", "inventory_bp_v2"),),
        ),
    ),
    settings=(
        SettingField(
            "checkout_max_days",
            "int",
            default=14,
            label="Longest checkout (days)",
            description="Default due date for new checkouts",
        ),
    ),
    nav=(
        NavItem(
            "/app/inventory",
            "shell.nav.inventory",
            "package",
            order=30,
            perms=("inventory.items.read",),
        ),
    ),
    tables=("inventory_items", "inventory_checkouts", "item_instructions"),
)
