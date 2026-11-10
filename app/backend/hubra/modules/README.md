# Modules

Every section of the club app is a module. The built-in ones each have a
manifest in this folder: core, members, roles, events, finance, functions,
groups, polls, posts, bindings and mail. Everything else (the books,
inventory, codes, keys, budgets, Discord, …) is a plugin with its own
repository; plugins declare their modules the same way, see
[docs/plugins.md](../../../../docs/plugins.md).

A club admin switches optional modules on or off under
**Settings > Modules**; a platform manager can block a module for a club
(`PUT /api/v1/app/features/tenants/<id>/<code>` with `{"allowed": false}`).

Switching a module off hides it and makes its API answer
`403 MODULE_DISABLED`. Its data stays in the database and comes back when the
module is switched on again.

## Where things are

| What | Where |
| --- | --- |
| Manifest types, registry, state, gate, event bus | `hubra/core/modules/` |
| One manifest per built-in module | this folder |
| Club admin API | `GET /api/v1/app/modules`, `PUT /api/v1/app/modules/<code>`, `PUT /api/v1/app/modules/<code>/settings` |
| CLI | `flask modules list|enable|disable|sync [--tenant <slug>]` |
| Frontend | sidebar built from `GET /modules`; `RequireModule` and `useModules()` in `app/frontend/src/modules/` |

## Adding a module

A new feature with its own models and screens is usually a plugin: start
from [hubra-plugins-template](https://github.com/hubra-app/hubra-plugins-template).
A built-in module is one file here whose manifest points at code in
`hubra/api/<area>/` and `hubra/core/`:

```python
from hubra.core.modules import Blueprint, Module, NavItem, SettingField

module = Module(
    code="polls",
    name="Polls",
    description="Member polls and voting",
    default_enabled=True,
    depends_on=("members",),
    blueprints=(
        Blueprint("hubra.api.polls.routes", "polls_bp", "/api/v1/app/polls"),
    ),
    settings=(SettingField("notify_members", "bool", default=True),),
    nav=(NavItem("/app/operations/polls", "shell.nav.polls", "chart-bar"),),
    tables=("polls", "poll_options", "poll_votes", "poll_proxies"),
    tasks=("hubra.core.tasks.reminder_tasks",),
)
```

Then:

1. Import the module's models from `hubra/core/models/__init__.py` so
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

Give the standard roles access when a club first switches the module on
with `role_defaults={"member": "view", "board": "edit"}`; without it only
admins see the module until a role gets access (docs/roles.md).

Permission keys follow the blueprint name:
`polls_bp` + `@permission_required("polls", "read")` gives `polls.polls.read`.
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
never sent back to the browser, are stored encrypted (`enc:` + Fernet), and
saving an empty secret keeps the stored one. The settings page renders a
form from the schema.

`settings_page=` names the module's own settings page in the club app
(`/app/finance/settings`), for a module whose settings need more than the
generic form. Einstellungen › Module then links there instead of opening the
form. Put that page in the module's last tab, "Einstellungen"; any page can
also open the generic form with `/app/settings/modules?module=<code>`
(docs/settings/structure.md).

## Connected apps

`apps=` lists outside services a club can connect through the module
(Einstellungen › Verbundene Apps), as `AppProvider(code, name, handler,
scopes=(AppScope(...),))`. Core does the parts every service shares: the
`apps.manage` permission, the signed, browser-bound sign-in round trip, the
admin's confirmation, encrypted secrets, disconnecting, the audit log and
the activity list. The handler only supplies the service's own steps; the
hooks are listed in `hubra/core/apps.py`. Look a connection up by the
outside id with `apps.active(code, external_id)`, check `apps.has_scope()`
before acting, and note what happened with `apps.record()`.

## Events

`hubra.core.modules.emit("invoice.overdue", member_id=..., invoice_id=...)`
calls every subscriber whose module is on for the club, synchronously and in
the caller's transaction. A failing handler is logged and does not stop the
others. Event names live in `hubra/core/modules/events.py`.

## Background jobs

List a module's Celery task modules in `tasks=` so the worker loads them
(see `polls.py`). Tasks queued during a request carry the club in a
`tenant_id` header and run in that club's schema. Periodic jobs that work on club data use
`@per_tenant_job("<code>")`, which runs the body once per active club that has
the module on.
