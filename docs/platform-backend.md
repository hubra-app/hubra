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
| API paths | everything except the three below | `/api/v1/manager`, `/api/v1/admin`, `/api/v1/system` |
| Shared paths | `/health`, `/api/v1/health`, `/api/v1/version`, `/api/v1/instance` | same |
| Celery | `celery-worker`: the default queue (invoices, reminders, mail, push, Discord bot, plugin jobs) | `platform-worker`: queue `platform` (backups and restores, health and infra checks, upgrades, plugin updates, quotas, platform alerts, platform Discord log) |
| Start-up | waits until the schema is migrated (`python -m hubra.core.schema_wait`) | runs the init step: `flask db upgrade`, `sync-permissions`, `seed`, `ensure-superadmins`, `plugins sync`, `modules seal-secrets` |
| Celery beat | | runs the platform image |

The lists live in one place, `app/backend/hubra/core/roles.py`
(`PLATFORM_PREFIXES`, `PLATFORM_TASK_MODULES`).

Every role still registers every route; a backend answers 404 ("Not served by
the club backend") for the other side's paths before any other code runs. So
the permission sync and the permission list see every route, whichever pod
runs them.

### Routing

The browser keeps calling one API host. The split is by path:

- **k3s:** the `api.` rule in the Ingress sends the three platform prefixes to
  the `platform-backend` Service, everything else to `backend`
  (`deploy/app/ingress.yaml`, the overlays' `ingress.yaml`).
- **Compose:** the frontend nginx sends them to `PLATFORM_API_UPSTREAM`
  (`app/deploy/nginx/40-hubra-runtime.sh`), set by
  `docker-compose.platform.yml`.

No frontend, cookie or CORS change is needed.

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
      - "traefik.http.routers.hubra-platform-api.rule=Host(`${HUBRA_API_HOST:-api.hubra.club}`) && (PathPrefix(`/api/v1/manager`) || PathPrefix(`/api/v1/admin`) || PathPrefix(`/api/v1/system`))"
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
