# Platform backend

The backend can run as two separate deployments from the same code:

- the **club backend** (`backend`, `celery-worker`, `discord-gateway`): the club
  app, sign-in and accounts, everything members use;
- the **platform backend** (`platform-backend`, `platform-worker`): the
  platform API that manage uses, platform background jobs, migrations and the
  scheduler.

A platform change (an alert rule, a backup fix, a new manage page) then rolls
only the platform pods. Members never notice it.

Compose installs keep one backend by default (`HUBRA_ROLE` unset means
`all`). `deploy/app` and the Contabo overlay run split.

## What runs where

| | Club backend | Platform backend |
| --- | --- | --- |
| Image | `ghcr.io/hubra-app/hubra/backend` | `ghcr.io/hubra-app/hubra/platform-backend` (the same build, published under a second name) |
| `HUBRA_ROLE` | `club` | `platform` |
| API paths | `/api/v1/app` (club app), `/api/v1/global` (sign-in, account, public), plugin routes | `/api/v1/platform` |
| Shared paths | `/health`, `/api/v1/global/health`, `/api/v1/global/version`, `/api/v1/global/instance` | same |
| Celery | `celery-worker`: the default queue (invoices, reminders, mail, push, Discord bot, plugin jobs) | `platform-worker`: queue `platform` (backups and restores, health and infra checks, upgrades, plugin updates, quotas, platform alerts, platform Discord log) |
| Start-up | waits until the schema is migrated (`python -m hubra.core.schema_wait`) | runs the init step: `flask db upgrade`, `sync-permissions`, `seed`, `ensure-superadmins`, `plugins sync`, `modules seal-secrets` |
| Celery beat | | runs the platform image |

The API areas and the old paths that lead to them are in
`app/backend/hubra/core/api_areas.py` (see [API areas](#api-areas) below); the
task list is in `app/backend/hubra/core/roles.py` (`PLATFORM_TASK_MODULES`).

Every role still registers every route; a backend answers 404 ("Not served by
the club backend") for the other side's paths before any other code runs. So
the permission sync and the permission list see every route, whichever pod
runs them.

### Routing

The browser keeps calling one API host. The split is by path:

- **k3s:** the `api.` rule in the Ingress sends `/api/v1/platform` and the old
  platform paths (`/api/v1/manager`, most of `/api/v1/system`) to the
  `platform-backend` Service, everything else to `backend`
  (`deploy/app/ingress.yaml`, the overlays' `ingress.yaml`).
- **Compose:** the frontend nginx sends them to `PLATFORM_API_UPSTREAM`
  (`app/deploy/nginx/40-hubra-runtime.sh`), set by
  `docker-compose.platform.yml`.

`tests/test_api_areas.py` checks that the Ingress files and the nginx pattern
route every old and new path to the backend that serves it.

### API areas

| Area | Who calls it | Backend |
| --- | --- | --- |
| `/api/v1/platform/...` | manage: platform settings, plugins (`/platform/plugins`), backups (`/platform/backups`), the support desk (`/platform/support`), all clubs and club admin (`/platform/system/...`) | platform |
| `/api/v1/app/...` | the club app: members, events, finance, mail, ..., club admin settings (`/app/admin`), the permission catalogue (`/app/permissions`) | club |
| `/api/v1/global/...` | everyone: sign-in (`/global/auth`), the account (`/global/account`), translations, version, status, public pricing, plugin frontends, the club directory, invites, join and club requests, ending a support session | club |

Sign-in is in `/global`, on the club backend, on purpose: every signed-in
person refreshes a token every 15 minutes, so a platform rollout must not
touch it.

**Old paths still work.** `/api/v1/members`, `/api/v1/manager/platform/...`,
`/api/v1/system/...` and the others are rewritten to the new path before the
URL is matched (`LegacyApiPaths`), so older app versions in open browser tabs,
plugins and links in sent mail keep working. Plugins keep their own prefix
(`/api/v1/keys`, `/api/v1/bank`, ...) and run on the club backend.

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

**The platform release must be the same as the club release or newer.**

- **Normal release:** bump both tags to the same version. The platform pod
  migrates; the new club pod waits for that, then starts. The old club pod
  keeps serving until the new one is ready.
- **Platform-only fix:** bump only the platform tag. Club pods don't restart.
- **Club tag ahead of the platform tag:** if that release has new
  migrations, the new club pod waits (`schema-wait` init container, 15 minutes,
  then it restarts and waits again) and the old club pod keeps serving. Nothing
  breaks; the rollout just doesn't finish until the platform catches up.
- **Rolling the platform back** below a release whose migrations already ran
  fails in `flask db upgrade` (the database knows a revision the old image
  doesn't). That was true before the split too: roll forward instead.

Beat runs the platform image for the same reason: it holds every schedule,
club ones included, so it must be at least as new as the club code.

## Updating

### k3s (Contabo overlay)

`deploy/clusters/contabo/kustomization.yaml` pins each image:

```yaml
images:
  - name: ghcr.io/hubra-app/hubra/backend
    newTag: 1.5.0
  - name: ghcr.io/hubra-app/hubra/platform-backend
    newTag: 1.5.1   # platform-only fix on top of 1.5.0
```

A release publishes both names with the same tags (`images.yml` copies the
backend manifest to `platform-backend`, no second build).

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

Both API Deployments use `maxSurge: 1, maxUnavailable: 0`: the new pod must
pass its readiness probe before the old one stops, even with one replica. A
`preStop` sleep of 10 seconds keeps the old pod answering while Traefik takes
it out of rotation; without it, requests already routed to a stopping pod fail
with 502. The platform worker gets five minutes to finish a running backup or
restore before it is stopped.

## Moving an existing cluster to the split

1. Publish a release (or run Images by hand) from a commit that has this
   change, so `platform-backend` exists in GHCR with the same tags as `backend`.
   The workflow creates the new package. Check in the org's Packages that
   `platform-backend` has the same visibility as `backend`, so the
   `ghcr-pull` token can pull it.
2. Set both tags in the overlay to that build in the same commit.
3. Flux applies it: `platform-backend` runs the migrations, the new `backend`
   pod waits for them, the Ingress starts sending the platform paths to
   `platform-backend`, and `platform-worker` starts taking the platform queue.
4. Check manage › Diagnose › Builds: it lists `Platform backend (API)` and
   `Platform worker` next to the club processes.

Tasks already queued on the default queue when the switch happens still run
on the club worker (it has the same code); only new ones go to `platform`.

## Not split (yet)

- **Database rights.** Both backends use the same Postgres role. A separate,
  narrower role per side needs an audit of which platform tables club code
  writes (see the recommendation in PR #146).
- **Network access.** The platform paths are on the public API host. An IP
  allowlist or Cloudflare Access on them is an Ingress middleware away and
  doesn't need code changes.
- **Frontends.** Still one repo and one image each; see
  [platform-split-frontends.md](platform-split-frontends.md).
