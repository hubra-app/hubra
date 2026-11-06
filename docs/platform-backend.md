# Split backends: app, global and platform

The backend runs as three deployments from the same code, one per API area:

- the **app backend** (`backend`, `celery-worker`, `discord-gateway`): the
  club app (`/api/v1/app`) and plugin routes, and the club background jobs;
- the **global backend** (`global-backend`): sign-in, the account,
  translations, the club directory, invites and public data
  (`/api/v1/global`);
- the **platform backend** (`platform-backend`, `platform-worker`): the
  platform API that manage uses (`/api/v1/platform`), platform background
  jobs, migrations and the scheduler.

Each has its own image name, so each can be pinned, rolled and scaled on its
own: a platform change (an alert rule, a backup fix, a new manage page) rolls
only the platform pods, a club app release doesn't restart sign-in, and a busy
club evening can get more app pods without more of the others.

Compose installs keep one backend by default (`HUBRA_ROLE` unset means
`all`); `docker-compose.platform.yml` splits off the platform there, with
sign-in staying on the club backend (`HUBRA_ROLE=club` = app + global).
A Kubernetes install usually runs all three (its manifests live in the
cluster's own repository, not here).

## What runs where

| | App backend | Global backend | Platform backend |
| --- | --- | --- | --- |
| Image | `ghcr.io/hubra-app/hubra/app-backend` | `ghcr.io/hubra-app/hubra/global-backend` | `ghcr.io/hubra-app/hubra/platform-backend` |
| `HUBRA_ROLE` | `app` | `global` | `platform` |
| API paths | `/api/v1/app`, plugin routes | `/api/v1/global` | `/api/v1/platform` |
| Shared paths | `/health`, `/api/v1/global/health`, `/api/v1/global/version`, `/api/v1/global/instance` | same | same |
| Celery | `celery-worker`: the default queue (invoices, reminders, mail, push, Discord bot, plugin jobs) | none (its tasks go to the default queue) | `platform-worker`: queue `platform` (backups and restores, health and infra checks, upgrades, plugin updates, quotas, platform alerts, platform Discord log) |
| Start-up | waits until the schema is migrated (`python -m hubra.core.schema_wait`), then fills the club permission catalog (`flask sync-permissions`) | waits, the same | runs the init step: `flask db upgrade`, `sync-permissions`, `seed`, `ensure-superadmins`, `plugins sync`, `modules seal-secrets` |
| Celery beat | | | runs the platform image |

### Images

One Dockerfile (`app/backend/Dockerfile`), four images:

| Image | Target | Holds | `HUBRA_ROLE` |
| --- | --- | --- | --- |
| `backend` | `backend` (the default) | every file | unset (`all`): Compose |
| `app-backend` | `role`, `ROLE=app` | the app role's files | `app` |
| `global-backend` | `role`, `ROLE=global` | the global role's files | `global` |
| `platform-backend` | `role`, `ROLE=platform` | the platform role's files | `platform` |

A role image holds only the `hubra` modules on its role's list
(`scripts/role_files.py <role> --prune` in the build, see
[Code per role](#code-per-role)) and sets `HUBRA_ROLE` itself, so every
process started from it (API, worker, beat, the init step) is that role and
never tries to load another area's routes. All four share the base layers
(Python packages, Postgres clients, Pango), so they cost little registry
space.

`images.yml` rebuilds a role image only when a file on its list changed
(or its Dockerfile or `role_files.py`); otherwise the run gives the last
build its tags and the digest stays, so a deploy pinned by digest doesn't
restart it. A change to a club page leaves `platform-backend` and
`global-backend` alone; a change to a manage page leaves `app-backend` and
`global-backend` alone. A change to Hubra's core, the models, the
migrations or a club service most roles use rebuilds them all: most of the
backend's code is on every list. Each release still has one version for
all of them, and its `images.yaml` pins each image by its own digest.

On Kubernetes the app backend, its worker and the Discord gateway run
`app-backend`. A cluster pinned to a build from before the role images can
point `app-backend` at that `backend` build until it pins a release that has
`app-backend`.

The API areas and the old paths that lead to them are in
`app/backend/hubra/core/api_areas.py` (see [API areas](#api-areas) below); the
task list is in `app/backend/hubra/core/roles.py` (`PLATFORM_TASK_MODULES`).

Each role registers, and imports, only its own area's routes and the shared
ones (probes, version, OAuth server metadata): `hubra.core.roles.registers`
decides from each blueprint's URL prefix in the module manifests, and
`Blueprint(..., shared=True)` marks the shared ones. A backend answers 404
("Not served by the app backend") for another area's paths before any other
code runs. So the platform backend holds no club routes and the app backend
no sign-in or manage routes, and each role's image only needs the code its
own routes and Hubra's core import (see [Code per role](#code-per-role)).

Plugin code is club code: the global and platform backends (and the
platform worker and beat) read each installed plugin's manifest (its
package's `module`, for the catalogue, migrations, tables and the public
plugin list) but import none of its routes, models or task modules
(`hubra.core.plugins.loader.MANIFEST_ONLY_ROLES`). A plugin's code can then
only break the app backend and its worker, not sign-in or manage.
Connected-app hooks and event handlers of plugins stay names and are
imported when called.

The club permission catalog comes from the club routes and plugins, so only
a backend that loads them fills it (`roles.loads_club_routes`: roles `all`,
`club`, `app`). On Kubernetes that is an init container of the app backend that runs
`flask sync-permissions` after `python -m hubra.core.schema_wait`; with `docker-compose.platform.yml` the
`club-init` step. The platform init step runs from the platform image, which
sets `HUBRA_ROLE=platform` itself, so it seeds only the platform roles. A club
permission checked by a route of another area (connected apps and
translation suggestions, on the global backend) is declared in the `core`
module's `permissions` too, so the app backend keeps it in the catalog;
`tests/test_backend_roles.py` checks that none is missing. Manage's list of
guarded endpoints, on the platform backend, shows the permissions of routes
it doesn't load from that catalog, without path and method.

### Code per role

`app/backend/scripts/role_files.py <role>` lists the files a role needs:
all of `hubra.core` and the module manifests, the role's blueprint modules,
and everything they import (followed through every `import` in the source,
also inside functions), plus every file that isn't a `hubra` module
(migrations, templates, seed data). Most club services are in every list,
because core and the platform's club pages use them (a new club's starter
groups, adding a club admin, privacy requests). What one role has alone is
its routes: the club app's pages, sign-in and the account, or manage's
platform pages and backups.

`tests/test_role_files.py` starts each role (app, Celery with its task
modules, the CLI) and fails if it imported a module outside its list, and
checks that the script picks the same blueprints as `roles.registers`.

### Routing

The browser keeps calling one API host. The split is by path:

- **Kubernetes:** the `api.` rule of the cluster's Ingress must send
  `/api/v1/platform` and the old platform paths (`/api/v1/manager/...`, most
  of `/api/v1/system`) to the `platform-backend` Service, `/api/v1/global`
  and its old paths (`/api/v1/auth`, `/api/v1/account`, `/api/v1/i18n`, ...)
  to `global-backend`, everything else to `backend`. The exact path lists are
  `platform_paths` and `global_paths` in `app/deploy/nginx/40-hubra-runtime.sh`
  (checked against the routes by `tests/test_api_areas.py`).
- **Compose:** the frontend nginx sends them to `PLATFORM_API_UPSTREAM` and
  `GLOBAL_API_UPSTREAM` when set (`app/deploy/nginx/40-hubra-runtime.sh`);
  `docker-compose.platform.yml` sets the platform one.

`tests/test_api_areas.py` checks that the Ingress files and the nginx patterns
route every old and new path to the backend that serves it.

A path with the club in it (`/api/<slug>/v1/...`, from before the club moved
to a header) can't be split by an Ingress prefix, so it always reaches the app
backend, which answers only club paths that way (it doesn't load the global
routes). The frontends send the club as a header and never use these paths.

### API areas

| Area | Who calls it | Backend |
| --- | --- | --- |
| `/api/v1/platform/...` | manage: platform settings, plugins (`/platform/plugins`), backups (`/platform/backups`), the support desk (`/platform/support`), all clubs and club admin (`/platform/system/...`) | platform |
| `/api/v1/app/...` | the club app: members, events, finance, mail, ..., club admin settings (`/app/admin`), the permission catalogue (`/app/permissions`) | app |
| `/api/v1/global/...` | everyone: sign-in (`/global/auth`), the account (`/global/account`), translations, version, status, public pricing, plugin frontends, the club directory, invites, join and club requests, ending a support session | global |

Sign-in has its own backend on purpose: every signed-in person refreshes a
token every 15 minutes and every page load asks for the account, so neither a
platform nor a club app rollout should touch it, and its load (many small
requests) scales differently from the club app's.

**Old paths still work.** `/api/v1/members`, `/api/v1/manager/platform/...`,
`/api/v1/system/...` and the others are rewritten to the new path before the
URL is matched (`LegacyApiPaths`), so older app versions in open browser tabs,
plugins and links in sent mail keep working. Plugins keep their own prefix
(`/api/v1/keys`, `/api/v1/bank`, ...) and run on the app backend; their
frontend files (`/api/v1/global/plugins/...`) come from the global backend.

**URLs registered outside Hubra keep the old form for now:** the Discord
OAuth callbacks (`/api/v1/apps/callback/discord`,
`/api/v1/account/linked-accounts/discord/callback`) and the interactions
endpoint (`/api/v1/discord/interactions`) are what the Discord Developer
Portal knows. They keep working through the rewrite; switch them in the
portal and in the code together when you want.

### Background jobs

With `HUBRA_PLATFORM_QUEUE=platform`, every process that sends a task routes the
platform task modules to the `platform` queue. Set it on **every** backend
process of a split install (the manifests and the Compose overlay do). Without
it, all tasks stay on the default queue, which is right for a single worker.

## The version rule

Migrations run in one place: the platform backend's init step. So:

**The platform release must be the same as the app and global releases or
newer.**

- **Normal release:** bump all three tags to the same version. The platform
  pod migrates; the new app and global pods wait for that, then start. The old
  pods keep serving until the new ones are ready.
- **Platform-only fix:** bump only the platform tag. Nothing else restarts.
- **App- or global-only fix:** bump only that tag (the platform tag must
  already be at that version or newer if the fix has migrations).
- **App or global tag ahead of the platform tag:** if that release has new
  migrations, the new pod waits (`schema-wait` init container, 15 minutes,
  then it restarts and waits again) and the old pod keeps serving. Nothing
  breaks; the rollout just doesn't finish until the platform catches up.
- **App and global on different releases** is fine for a fix in one of them,
  but keep them close: a new club app may call a global route that only the
  newer global release has.
- **Rolling the platform back** below a release whose migrations already ran
  fails in `flask db upgrade` (the database knows a revision the old image
  doesn't). That was true before the split too: roll forward instead.

Beat runs the platform image for the same reason: it holds every schedule,
club ones included, so it must be at least as new as the club code.

## Updating

### Kubernetes

Pin each image in the cluster's repository, for example:

```yaml
images:
  - name: ghcr.io/hubra-app/hubra/app-backend
    newTag: 1.5.0
  - name: ghcr.io/hubra-app/hubra/global-backend
    newTag: 1.5.0
  - name: ghcr.io/hubra-app/hubra/platform-backend
    newTag: 1.5.1   # platform-only fix on top of 1.5.0
```

A release tags every image with its version; a role image whose files did
not change keeps its last build's digest (see [Images](#images)). The release
also lists every image pinned by digest, ready to paste.

`backend`, `global-backend` and `platform-backend` take any number of
replicas (the init step takes turns, `hubra.core.startup_lock`), and so do
`celery-worker` and `platform-worker`. Beat and the Discord gateway stay at
one ([scaling.md](scaling.md)).

### Compose

```sh
# in .env
COMPOSE_FILE=docker-compose.yml:docker-compose.platform.yml
HUBRA_VERSION=1.5.0
HUBRA_PLATFORM_VERSION=1.5.1

# platform-only update: the club containers keep running
docker compose up -d flask-init platform-backend platform-worker celery-beat
```

With `docker-compose.traefik.yml` the API host needs a second router for the
platform paths, with a higher priority than the API router:

```yaml
  platform-backend:
    networks: [hubra_internal, frontend]
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=frontend"
      - "traefik.http.routers.hubra-platform-api.rule=Host(`${HUBRA_API_HOST:-api.hubra.club}`) && (PathPrefix(`/api/v1/platform`) || PathPrefix(`/api/v1/manager`) || PathRegexp(`^/api/v1/system(/|$)`)) && !PathRegexp(`^/api/v1/system/(clubs|invites|join-requests|tenant-requests/mine|impersonation|permissions)(/|$)`)"
      - "traefik.http.routers.hubra-platform-api.priority=100"
      - "traefik.http.routers.hubra-platform-api.entrypoints=websecure"
      - "traefik.http.routers.hubra-platform-api.tls.certresolver=letencrypt"
      - "traefik.http.services.hubra-platform-api.loadbalancer.server.port=5000"
```

## Rollouts without a gap

All three API Deployments use `maxSurge: 1, maxUnavailable: 0`: the new pod must
pass its readiness probe before the old one stops, even with one replica. A
`preStop` sleep of 10 seconds keeps the old pod answering while Traefik takes
it out of rotation; without it, requests already routed to a stopping pod fail
with 502. The platform worker gets five minutes to finish a running backup or
restore before it is stopped.

## Moving an existing cluster to the split

1. Publish a release (or run Images by hand) from a commit that has this
   change, so `app-backend`, `global-backend` and `platform-backend` exist
   in GHCR. The workflow creates the new packages. Check in
   the org's Packages that all three have the same visibility as `backend`, so the
   `ghcr-pull` token can pull them.
2. Set all three role images in the overlay to that build in the same
   commit.
3. Flux applies it: `platform-backend` runs the migrations, the new `backend`
   and `global-backend` pods wait for them, the Ingress starts sending each
   area to its backend, and `platform-worker` starts taking the platform
   queue.
4. Check manage › Diagnose › Builds: it lists `Sign-in & account (API)`,
   `Platform backend (API)` and `Platform worker` next to the club processes.

Tasks already queued on the default queue when the switch happens still run
on the club worker (it has the same code); only new ones go to `platform`.

## Shared code and area code

Each role image holds only its role's files and answers only its own paths
(`hubra/core/roles.py`). That works because the code keeps one direction:

- `hubra/core` is shared by every backend: models, migrations, sign-in and
  tokens (`core/auth`), permissions, settings, notifications, version and
  health. A change here concerns all three.
- `hubra/api/<area package>` is route code. It imports core; core never
  imports it.

`tests/test_import_boundaries.py` checks this on every import, also lazy
ones inside functions. Its `CORE_TO_API_LEFT` lists the core modules that
still use club code (club schemas, a new club's starter data, club tasks);
the list may only shrink. Old module names that plugins import
(`hubra.api.permissions`, `hubra.api.utils`, `hubra.api.auth.helpers`,
`hubra.api.notifications.services`) stay as aliases of the moved modules;
Hubra's own code uses the new names.

## Not split (yet)

- **Database rights.** All backends use the same Postgres role. A separate,
  narrower role per side needs an audit of which platform tables club code
  writes (see the recommendation in PR #146).
- **Network access.** The platform paths are on the public API host. An IP
  allowlist or Cloudflare Access on them is an Ingress middleware away and
  doesn't need code changes.
- **Frontends.** Still one repo and one image each; see
  [platform-split-frontends.md](platform-split-frontends.md).
