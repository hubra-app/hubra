# Modules

Every section of the suite is a module: members, groups, finance, inventory,
mail and so on. A club admin switches optional modules on or off under
**Settings > Modules**; a platform manager can block a module for a club
(manager API `PUT /api/v2/manager/features/tenants/<id>/<code>` with
`{"allowed": false}`).

Switching a module off hides it and makes its API answer
`403 MODULE_DISABLED`. Its data stays in the database and comes back when the
module is switched on again.

## Where things are

| What | Where |
| --- | --- |
| Manifest types, registry, state, gate, event bus | `hubra/core/modules/` |
| One manifest per module | this folder |
| Club admin API | `GET /api/v1/modules`, `PUT /api/v1/modules/<code>`, `PUT /api/v1/modules/<code>/settings` |
| CLI | `flask modules list|enable|disable|sync [--tenant <slug>]` |
| Frontend | sidebar built from `GET /modules`; `RequireModule` and `useModules()` in `app/frontend/src/modules/` |

## Adding a module

Small modules live in one file here (`codes.py`). A module with its own
models, routes and services gets a package (`inventory_keys/`,
`finance_budgets/`) that holds all
of them:

```
hubra/modules/inventory_keys/
    __init__.py      # the manifest: `module = Module(...)`
    models.py
    routes.py        # a Blueprint
    services.py
    hooks.py         # event handlers, optional
```

```python
from hubra.core.modules import Blueprint, Module, NavItem, SettingField

module = Module(
    code="inventory.keys",
    name="Keys",
    description="Physical keys, who holds them, and handovers",
    depends_on=("inventory",),
    default_enabled=False,
    blueprints=(
        Blueprint(
            "hubra_keys.routes",
            "keys_bp",
            "/api/v1/keys",
            v2=(("/api/v2/tenants/keys", "keys_bp_v2"),),
        ),
    ),
    settings=(SettingField("handover_requires_signature", "bool", default=False),),
    events={"invoice.overdue": "hubra_keys.hooks:on_overdue"},
    tables=("keys", "key_handovers"),
)
```

Then:

1. Import the package's models from `hubra/core/models/__init__.py` so
   Alembic and `db.create_all()` see them.
2. List the module's tenant tables in `tables=`. New club schemas clone
   exactly these (`tests/tenant/test_schema_manager.py` fails if a table is
   missing).
3. Write an Alembic migration (`flask db migrate`), and run `flask modules
   sync` (or `flask seed`) so the catalog gets a row.
4. Frontend: wrap the module's routes in `<RequireModule code="...">`, hide
   its tabs with `useModules().has("...")`, and add its `nav` icon name to
   `NAV_ICONS` in `components/Shell/nav.tsx`. The sidebar entry itself comes
   from the manifest.

Permission keys follow the blueprint name as before:
`keys_bp` + `@permission_required("keys", "read")` gives `keys.keys.read`.
Run `flask sync-permissions` after adding routes.

## Rules the registry enforces

- Codes are unique and every `depends_on` entry exists; no cycles.
- A `required` module can only depend on other required modules.
- A module is only on when everything it depends on is on. Switching on a
  module whose dependency is off is refused (`409 MODULE_DEPENDENCY_OFF`),
  and so is switching off a module that an enabled module needs
  (`409 MODULE_HAS_DEPENDENTS`).

## Settings

`settings=` declares the module's per-club settings. Values are validated
against the field type, stored in `TenantFeature.config`, and read with
`hubra.core.modules.get_config("<code>")`. Fields of type `secret` are
never sent back to the browser, and saving an empty secret keeps the stored
one. The settings page renders a form from the schema.

## Events

`hubra.core.modules.emit("invoice.overdue", member_id=..., invoice_id=...)`
calls every subscriber whose module is on for the club, synchronously and in
the caller's transaction. A failing handler is logged and does not stop the
others. Event names live in `hubra/core/modules/events.py`.

## Background jobs

List a module's Celery task modules in `tasks=` so the worker loads them
(see `discord/`). Tasks queued during a request carry the club in a
`tenant_id` header and run in that club's schema. Periodic jobs that work on club data use
`@per_tenant_job("<code>")`, which runs the body once per active club that has
the module on.
