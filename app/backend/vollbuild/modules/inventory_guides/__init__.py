"""Guides: a how-to per machine or tool, in Markdown or as a Drive link."""

from vollbuild.core.modules import Blueprint, Module

module = Module(
    code="inventory.guides",
    name="Guides",
    description="Usage guides for machines and tools (Markdown or a Google Drive link)",
    default_enabled=False,
    depends_on=("inventory",),
    blueprints=(
        Blueprint(
            "vollbuild.modules.inventory_guides.routes",
            "guides_bp",
            "/api/v1/guides",
            v2=(("/api/v2/tenants/guides", "guides_bp_v2"),),
        ),
    ),
    # Columns on inventory_items; shown in the item panel, no nav entry.
)
