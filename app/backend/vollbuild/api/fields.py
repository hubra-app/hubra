"""Field-level permission registry.

Maps (blueprint, resource) → {field_name: display_name} for every resource
that supports per-field update permissions.

Permission keys follow the convention::

    {blueprint}.{resource}.update.{field}

A coarse ``{blueprint}.{resource}.update`` permission grants ALL fields.
Field-level permissions are only needed when coarse is absent — they allow
a role to update specific fields without full update access.

The registry is walked by ``flask sync-permissions`` to auto-create
Permission rows for every declared field.
"""

from __future__ import annotations

# Blueprint names are the stripped forms (without ``_bp`` suffix).
# They must match what ``_derive_perm_key`` in permissions.py produces.

FIELD_REGISTRY: dict[tuple[str, str], dict[str, str]] = {
    # ── Members ───────────────────────────────────────────────────────────
    ("members", "members"): {
        "first_name": "First name",
        "last_name": "Last name",
        "email": "Private email",
        "status": "Status",
        "tier_id": "Membership tier",
        "role_ids": "Roles",
        "group_ids": "Groups",
        "tool_hours": "Tool hours",
        "notes": "Notes",
        "avatar_color": "Avatar color",
        "joined": "Join date",
        "club_username": "Club username",
        "must_change_password": "Force password change",
        "address_street": "Street address",
        "address_house_no": "House number",
        "address_postal_code": "Postal code",
        "address_city": "City",
        "address_country": "Country",
        "forwarding_enabled": "Mail forwarding",
        "retention_days": "Mail retention days",
    },
    # ── Groups ────────────────────────────────────────────────────────────
    ("groups", "groups"): {
        "name": "Group name",
        "description": "Description",
        "color": "Color",
        "icon_name": "Icon",
        "lead_id": "Group lead",
    },
    # ── Tiers ─────────────────────────────────────────────────────────────
    ("tiers", "tiers"): {
        "name": "Tier name",
        "price_chf": "Price (CHF)",
        "color": "Color",
        "billing_cycle": "Billing cycle",
        "price_type": "Pricing type",
        "percentage_value": "Percentage value",
        "coefficient": "Coefficient",
        "round_to": "Round to",
    },
    # ── Finance: Invoices ─────────────────────────────────────────────────
    ("finance", "invoices"): {
        "status": "Invoice status",
        "due": "Due date",
        "notes": "Notes",
    },
    # ── Finance: Transactions ─────────────────────────────────────────────
    ("finance", "transactions"): {
        "category_id": "Category",
        "payee_name": "Payee",
        "notes": "Notes",
    },
    # ── Finance: Transaction Categories ───────────────────────────────────
    ("finance", "categories"): {
        "name": "Category name",
        "color": "Color",
    },
    # ── Inventory ─────────────────────────────────────────────────────────
    ("inventory", "items"): {
        "name": "Item name",
        "description": "Description",
        "location": "Location",
        "status": "Status",
        "owner_id": "Owner",
        "responsible_id": "Responsible person",
    },
    # ── Events ────────────────────────────────────────────────────────────
    ("events", "events"): {
        "title": "Title",
        "description": "Description",
        "start": "Start time",
        "end": "End time",
        "location": "Location",
        "max_attendees": "Max attendees",
    },
    # ── Functions ─────────────────────────────────────────────────────────
    ("functions", "functions"): {
        "name": "Function name",
        "description": "Description",
        "max_holders": "Max holders",
    },
    # ── Roles ─────────────────────────────────────────────────────────────
    ("roles", "roles"): {
        "name": "Role name",
        "description": "Description",
        "is_admin": "Admin flag",
    },
}


def field_perm_key(blueprint: str, resource: str, field: str) -> str:
    """Build the permission key for a field-level update permission."""
    prefix = blueprint.removesuffix("_bp")
    return f"{prefix}.{resource}.update.{field}"


def iter_field_perms():
    """Yield (key, display_name, resource, action, blueprint) for every field perm."""
    for (bp, resource), fields in FIELD_REGISTRY.items():
        for field, display_name in fields.items():
            key = field_perm_key(bp, resource, field)
            yield {
                "key": key,
                "display_name": display_name,
                "resource": resource,
                "action": f"update.{field}",
                "blueprint": bp,
            }
