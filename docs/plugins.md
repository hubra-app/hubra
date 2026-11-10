# What plugins can extend

Plugins are club features. They run in the club backend, on the club's
queue and in the club app. Manage, the platform API (`/api/v1/platform`) and
the global API (`/api/v1/global`: sign-in, account, public data) can't be
touched by a plugin. The design and its reasons are in the
[plugin extension areas doc](https://claude.ai/artifact/WokKbL3xuPmA6qrtAAEncC).

## Trust

| Signed by | Backend code | Processes, in-transaction events |
| --- | --- | --- |
| Hubra (official key) or shipped with Hubra | yes | yes |
| A key the platform admin trusts | yes, club level only | no |
| Nobody | refused unless an admin accepts it unsigned | no |

## Areas and `uses:`

A plugin lists the areas it uses in `plugin.yaml`. The loader refuses a
plugin that touches an area it didn't list. A plugin without `uses:` still
loads (plugins released before the list existed) and logs a warning;
the template's release check requires it.

```yaml
uses: [routes, events, jobs, tables, settings, nav, frontend]
depends:
  finance: ">=2.0,<3"
```

| Area | Manifest field | Limit |
| --- | --- | --- |
| `routes` | `Module.blueprints` | under `/api/v1/app/<name>`, a prefix nobody else has |
| `public` | `Module.public_endpoints` | listed by endpoint name |
| `events` | `Module.events` | delivered after the commit (below) |
| `jobs` | `Module.tasks`, `Module.schedule` | the default (club) queue |
| `processes` | `Module.processes` | official plugins only |
| `tables` | `Module.tables`, `migrations/` | own tables, never Hubra's |
| `settings` | `Module.settings` | per club |
| `apps` | `Module.apps` | connected apps |
| `nav` | `Module.nav` | club app sidebar |
| `frontend` | `frontend/dist/plugin.js` | club app pages, tabs and slots |
| `contracts` | `Module.provides`, `Module.consumes` | named `<module>.<what>`; use only what `consumes` lists ([contracts.md](contracts.md)) |
| `mail`, `discord` | (reserved) | plugin mail templates, Discord command registry |

Everything a manifest points at (blueprints, handlers, task modules,
scheduled tasks, processes, app handlers) must be in the plugin's own
package. The checks live in `app/backend/hubra/core/plugins/limits.py`.

## Files

A plugin that keeps files (uploads, generated PDFs) stores them through
Hubra's file store instead of the database or its own folder:

```python
from hubra.core import files

stored = files.put("documents", data, "application/pdf")  # a StoredFile record
data = files.read(stored.key)
files.remove(stored.key)
```

The platform decides where files go (S3 or a folder on the server), every
file is encrypted with the club's key, counts towards the club's storage and
is deleted with the club. Keep `stored.key` in your own table; `read` and
`remove` only find files of the club the request works in. `put` refuses
files larger than `files.max_mb` (`files.FileTooLarge`).

## Slots

A plugin's frontend can put a component into these places of the club app
(`slots` in `registerPlugin`); the props are typed in
`app/frontend/src/plugins/types.ts`:

| Slot | Where | Props |
| --- | --- | --- |
| `account.cards` | the member's own page (Konto) | none |
| `inventory.item` | an inventory item's page | `itemId` |
| `settings.module.actions` | a module's row in Einstellungen › Module | `code`, `configured`, `name` |
| `apps.connection` | a connected app's details | `connection`, `onChange` |
| `invoice.actions` | next to an invoice's buttons: the member's open invoices and the invoice page | `invoice`, `onChange` |
| `dashboard.stats` | the club overview's numbers row (Dashboard › Übersicht); render a `StatTile` | none |

## Route paths

Write new plugins with `/api/v1/app/<name>`. A plugin that names the old
form, `/api/v1/<name>`, is served under `/api/v1/app/<name>` and the old
path is rewritten to it, so its frontend and outside links keep working.
One prefix for core and plugin features means a feature that moves into a
plugin keeps its URLs.

### Extending a Hubra module

An official plugin may serve routes below the prefix of a module it depends
on, and keep that module's permission keys, so a feature that moves out of
Hubra keeps its URLs and every role keeps its rights:

```python
module = Module(
    code="finance.books",
    depends_on=("finance",),
    blueprints=(
        Blueprint("hubra_books.routes", "books_bp", "/api/v1/app/finance",
                  perm_prefix="finance"),
    ),
)
```

`perm_prefix` replaces the blueprint's name in its keys
(`finance.transactions.read`, not `books.transactions.read`). Other plugins
can only use their own module code.

## Events

Hubra's own modules get events inside the caller's transaction. A plugin's
handlers get them from the contract outbox: stored in the caller's
transaction, run in the worker after it commits, retried when the handler
fails ([contracts.md](contracts.md)). So a slow or failing plugin can't
hold up or roll back the caller's work, a rolled-back change never reaches
a plugin, and an event isn't lost when Redis is down. An official plugin
can keep in-transaction delivery for named events:

```python
module = Module(
    code="demo",
    events={"invoice.paid": "hubra_demo.hooks:on_paid"},
    events_in_transaction=("invoice.paid",),
)
```

Invoices announce themselves with `invoice.created` (`invoice_id`,
`category_id`), `invoice.updated` (`invoice_id`, `was_paid`, `changed`) and
`invoice.deleted` (`invoice_id`, `transaction_id`). Hubra's finance module
books the income that follows each invoice from these
(`hubra/api/finance/bookings.py`), and `invoice.paid` (`member_id`,
`invoice_id`) still comes when an invoice is paid.

In a plugin test that calls `emit()` directly, commit afterwards
(`db.session.commit()`): that is when the handler runs.

## Using another plugin

A plugin never imports another plugin, reads its tables or calls its REST
routes from the backend. It uses the other plugin's contracts: events it
publishes, actions it offers and queries it answers, by name and version,
through core. See [contracts.md](contracts.md).

## Dependencies

- `requires:` lists module codes (Hubra's or another plugin's).
- `depends:` lists other plugins by id with a version range.

Installing a plugin from a repository installs the plugins it depends on
first, from the same repository, in the newest version that fits the
range. An upload with a missing dependency is refused with what to install.
An update or rollback that an installed plugin's range excludes is refused,
and so is uninstalling a plugin that another one depends on.

### Add-ons

A plugin that needs another plugin is an **add-on** of it, its parent:
the first plugin under `depends:`, or else the plugin that provides the
first module under `requires:` (a Hubra module is no parent). The Plugin
catalogue shows add-ons inside their parent's card, and the index names
the parent of each plugin (`parent`). An add-on whose parent isn't
installed says so and can't be installed.

Name the parent under `depends:` with a version range, so Hubra can check
the version (the template's release check asks for it):

```yaml
requires: [inventory]          # the module the add-on uses
depends:
  inventory: ">=2.0,<3"        # the plugin that provides it, and which versions
```

An install or update whose range the installed parent misses stops with the
version it needs. With **Also update required plugins** on (Plugin catalogue,
off by default) it updates the parent first, from the same repository, to the
newest version in the range, unless the parent is held at its version.

### Taking over another plugin (`replaces:`)

When two plugins become one, the plugin that stays names the other under
`replaces:`:

```yaml
id: finances
modules: [finance.books, finance.budgets]   # the old plugin's module codes too
replaces: [budgets]
migrations: migrations                       # adopts the old plugin's tables
```

Installing or updating it takes the old plugin off the platform, in the same
step, like an uninstall that keeps the data:

- the old plugin's installed row and kept archives go, with a
  `replace_plugin` entry in the platform log;
- its tables stay. The new plugin's migrations adopt them: create a table
  only when it isn't there (`has_table`), add columns only when missing
  (`columns`), and never drop what the old plugin made;
- the clubs' module switches stay, because the new plugin offers the same
  module codes. Keep the old plugin's permission keys too (same blueprint
  names, or `perm_prefix`), so roles keep what they grant;
- contracts the old plugin offered can be offered by the new one under the
  same names.

The install is refused while another installed plugin still names the old
one under `depends:`, and the old plugin can't be installed again while the
new one is there. The loader never loads both: with both installed (an
older row, a development checkout) the old one shows "replaced by …". The
catalogue hides the old plugin unless it is still installed, and then says
which plugin to update; the new plugin's card lists what it takes over.

A rollback of the new plugin to a version without `replaces:` doesn't bring
the old plugin back: install it again (its data is still there).

### Renaming a module (`renamed_from`)

A module that gets a new code names its old ones, so each club keeps
whether it had the module on, and its settings:

```python
module = Module(code="qualifications", renamed_from=("inventory.guides",), ...)
```

Until a club changes something, its switch and settings are read from the
old code; the first change copies them to the new code. The catalogue row
of the new code starts with the default a manager set for the old one. A
plugin can't name a code that is still a loaded module. Permission keys
come from the blueprint names, so keep those to keep the roles' rights.
