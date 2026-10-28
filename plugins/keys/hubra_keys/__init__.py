"""Keys: physical keys, cards and fobs, who holds them, and every handover."""

from hubra.core.modules import Blueprint, Module, NavItem
from hubra.core.modules.events import INVOICE_OVERDUE

module = Module(
    code="inventory.keys",
    name="Keys",
    description="Physical keys, cards and fobs: who holds which, with a handover log",
    default_enabled=False,
    depends_on=("inventory",),
    blueprints=(
        Blueprint(
            "hubra_keys.routes",
            "keys_bp",
            "/api/v1/keys",
            v2=(("/api/v2/tenants/keys", "keys_bp_v2"),),
        ),
    ),
    nav=(
        NavItem(
            "/app/inventory/keys",
            "shell.nav.keys",
            "key",
            order=31,
            perms=("keys.keys.read",),
        ),
    ),
    events={INVOICE_OVERDUE: "hubra_keys.hooks:on_invoice_overdue"},
    tables=("keys", "key_handovers"),
)
