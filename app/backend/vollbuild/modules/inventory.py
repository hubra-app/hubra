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
        SettingField(
            "require_induction",
            "bool",
            default=True,
            label="Only inducted members can check out",
            description="Applies to items marked as needing instruction",
        ),
        SettingField(
            "block_when_overdue",
            "bool",
            default=False,
            label="Block checkouts while an invoice is overdue",
            description="More than 7 days past due; needs the Finance module",
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
