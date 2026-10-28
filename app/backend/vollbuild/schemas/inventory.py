"""Backwards-compatible re-export from vollbuild.core.schemas.inventory."""

from vollbuild.core.schemas.inventory import (
    EXCLUDE,
    RAISE,
    fields,
    validate,
    ma,
    InventoryItem,
    _CATEGORIES,
    _STATUSES,
    _VISIBILITIES,
    InventoryItemSchema,
    InventoryItemCreateSchema,
    InventoryItemUpdateSchema,
    InventoryCheckoutSchema,
    CheckoutCreateSchema,
)
