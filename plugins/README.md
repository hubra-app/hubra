# Plugins

A plugin adds features to Hubra without changing Hubra itself: backend
modules (routes, tables, settings, event hooks, Celery tasks) and screens in
the club app. The platform manager installs it once from the Marketplace,
and each club then switches its modules on or off in Settings › Modules, like
any built-in module.

The plugins in this folder ship with Hubra but are not active until a manager
installs them:

| Plugin        | Module(s)          | What it does                                     |
| ------------- | ------------------ | ------------------------------------------------ |
| `keys`        | `inventory.keys`   | Keys and access cards, handovers and deposits    |
| `guides`      | `inventory.guides` | Usage guides on inventory items                  |
| `budgets`     | `finance.budgets`  | Yearly budgets per transaction category          |
| `bank-import` | `finance.bank`     | Bank statement import (camt.053/054, MT940, CSV), invoice matching and booking rules |
| `discord`     | `discord`          | Announce events, posts and polls in Discord      |

The signing, repository and update design comes from
[labdex](https://github.com/labdex-app/labdex).

## For platform managers

**Install.** Manager portal › Plugins. Install a shipped plugin, one from a
repository, or upload a `.zip`. Installing runs the plugin's migrations in
every club and records it in the database; every API and Celery process
picks it up within `HUBRA_PLUGINS_RELOAD_POLL` seconds (15 by default)
without a new image. Each process unpacks installed plugins from the
database into its own `HUBRA_PLUGIN_DIR`, so no shared volume is needed.

**Trust.** Each archive carries a `SIGNATURE.json` over every file:

| Badge              | Meaning                                                              |
| ------------------ | -------------------------------------------------------------------- |
| Shipped with Hubra | In this folder of the image                                          |
| Official           | Signed with a key in `app/backend/hubra/core/plugins/keys/official/` |
| Community          | Signed with a key you trusted (Plugins › Signing keys)               |
| Unsigned           | Installs only after you tick "I trust this code"                     |
| Invalid signature  | Files changed after signing; refused                                 |

A plugin runs with full access to every club's data. Only the global
permission `plugins.manage` (Superadmin) can install one.

**Repositories.** Add the URL of a signed `index.json` and type the key id
the publisher gave you. The key is pinned: an index later signed with
another key is refused.

**Updates.** Plugins › Updates: _tell me_ (default) checks every six hours
and notes new and withdrawn versions in the audit log; _install official_
also installs updates from the official repository; _don't check_ turns it
off. Per plugin you can hold updates at a version, install an older version,
and roll back to the version the last update replaced. Rollback does not
undo migrations, so a plugin's migrations must keep the previous version
working.

**Uninstall.** The plugin's tables stay, so installing it again brings the
data back, unless you tick "also delete its data". Plugins other plugins
need can't be uninstalled first.

**Command line**, for single-club installs and scripts:

```
flask plugins list
flask plugins install keys                 # shipped, or from a repository
flask plugins install ./keys-1.0.0.zip [--accept-unsigned]
flask plugins uninstall keys [--delete-data]
flask plugins rollback keys
flask plugins repo-add https://example.org/plugins/index.json
flask plugins check-updates
flask plugins sync                          # on every deploy, after flask db upgrade
```

| Variable                    | Default                             | Meaning                                                           |
| --------------------------- | ----------------------------------- | ----------------------------------------------------------------- |
| `HUBRA_PLUGIN_DIR`          | `$TMPDIR/hubra-plugins-<uid>`       | Where a process unpacks installed plugins; any writable folder    |
| `HUBRA_BUNDLED_PLUGINS`     | `plugins/` of the checkout or image | Plugins shipped with this copy                                    |
| `HUBRA_PLUGINS_AUTOINSTALL` | empty                               | `all` or ids: count as installed without the database (dev/tests) |
| `HUBRA_PLUGINS_RELOAD_POLL` | `15`                                | Seconds between checks for installs by other processes; 0 = off   |
| `HUBRA_OFFICIAL_INDEX`      | `keys/official/index.url`           | The official repository                                           |

Deploying: run `flask plugins sync` after `flask db upgrade` (it brings
installed plugins' tables up to date in every club), start gunicorn from the
backend folder so it reads `gunicorn.conf.py` (the reload hook), and let the
container restart Celery: a worker exits after a plugin change so that it
starts again with the new set.

## For plugin authors

A plugin is a folder:

```
my-plugin/
  plugin.yaml
  CHANGELOG.md            # "## 1.1.0" sections; shown before updating
  .releaseignore          # left out of releases (tests/, frontend/src/, …)
  hubra_myplugin/         # the Python package; the name must start with hubra_
    __init__.py           # module = Module(...) or modules = [...]
    models.py             # SQLAlchemy models, imported on load
    routes.py
  migrations/             # Alembic revisions, one chain per plugin
  frontend/
    src/index.tsx         # registerPlugin({...})
    dist/plugin.js        # built; required in a release
  tests/
```

`plugin.yaml`:

```yaml
id: my-plugin
name: My plugin
version: 1.0.0
hubra: '>=0.1,<1' # Hubra versions it works with
description: 'One line: what it does'
author: Your Name
homepage: https://github.com/you/my-plugin
license: MIT
tags: [inventory]
package: hubra_myplugin
modules: [inventory.myplugin]
requires: [keys] # other plugins it needs (optional)
migrations: migrations
frontend: frontend/dist/plugin.js
```

**Backend.** The package defines `Module` objects exactly like the built-in
modules (see `app/backend/hubra/modules/README.md`): blueprints, settings,
nav entries, permissions, event hooks, tables. Module codes must not clash
with Hubra's. Look at `keys/` for a complete example.

**Tables.** Write migrations with `flask plugins revision my-plugin -m "..."
--autogenerate` (with `HUBRA_PLUGINS_AUTOINSTALL=my-plugin`). They run in
`public` and in every club's schema, each plugin with its own version table
(`alembic_version_my_plugin`). Use `hubra.core.plugins.ops.has_table()` to
make them idempotent, and keep downgrades to dropping your own tables.

**Frontend.** `frontend/src/index.tsx` registers what the plugin adds:

```tsx
import { registerPlugin } from '@hubra/plugin-sdk'
import translations from './translations.json'

registerPlugin({
  id: 'my-plugin',
  routes: [
    {
      path: 'inventory/things',
      module: 'inventory.myplugin',
      perm: 'things.read',
      component: ThingsScreen,
    },
  ],
  tabs: [
    {
      screen: 'finance',
      id: 'things',
      label: 'shell.nav.things',
      module: 'inventory.myplugin',
      component: ThingsTab,
    },
  ],
  slots: [{ slot: 'account.cards', module: 'inventory.myplugin', component: MyThingsCard }],
  translations, // { "en-GB": {...}, "de-CH": {...} }
})
```

Everything is shown only while its module is on for the club (and the user
has `perm`). Slots: `account.cards`, `inventory.item` (`{ itemId }`) and
`settings.module.actions` (`{ code, configured, name }`). The SDK
(`app/frontend/src/plugins/sdk.ts`) gives you the app's hooks, components
and API client. React, Mantine, react-query, react-router and react-i18next
come from the app at runtime; import them as usual. Anything else, such as
icons, is bundled.

Build it with the club app's toolchain:

```
cd app/frontend
npm run build:plugin -- ../../plugins/my-plugin      # or /path/to/my-plugin
npm run build:plugin -- --watch ../../plugins/my-plugin
npm run typecheck:plugins                              # plugins in this folder
```

The club app loads `/api/v1/plugins/<id>/frontend.js` of each plugin that
has a module on for the club.

**Tests.** `pytest` in `app/backend` also runs `plugins/*/tests` (with
`HUBRA_PLUGINS_AUTOINSTALL=all`). Use the backend's fixtures as usual.

## Publishing

```
flask plugins keygen me.pem                       # once; share me.pem.pub and its key id
flask plugins repo ./plugins ./public --key me.pem --name "My plugins"
flask plugins yank ./public my-plugin 1.0.1 --key me.pem --reason "breaks imports"
```

`repo` copies each plugin, leaves out what `.releaseignore` lists, signs it,
zips it and writes a signed `index.json` that keeps earlier versions. Serve
`./public` from any web server (GitHub Pages works), and give people the URL
of `index.json` and your key id. For plugins in their own repositories,
`flask plugins build-index sources.yaml ./public --key me.pem` builds the
index from their GitHub releases instead.

Single archives: `flask plugins sign ./my-plugin --key me.pem --signer "Your
Name"`, then `flask plugins pack ./my-plugin -o my-plugin-1.0.0.zip`.
