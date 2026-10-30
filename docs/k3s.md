# Running on Kubernetes (k3s)

The repo ships the app as plain Kustomize manifests. How they reach the
cluster is up to you: point your own GitOps tool (Flux, Argo CD) at one of the
directories below, or apply them by hand. The repo holds no GitOps config and
no cluster add-ons. Secrets stay out of git and are created once with
`deploy/create-secrets.sh`.

```
deploy/
├── app/                      # the app stack (base)
├── vollbuild-ch/             # overlay: the old vollbuild.ch hosts
├── clusters/contabo/         # overlay: hubra.club behind Cloudflare, CloudNativePG
└── create-secrets.sh         # .env -> Secret hubra-env (+ GHCR pull secret, Cloudflare)
modules/mail/k8s/             # the opt-in mail stack, see modules/mail/README.md
```

## What the cluster needs

- An ingress controller. `deploy/app` uses the class `traefik`, the one k3s
  ships.
- cert-manager with a ClusterIssuer named `letsencrypt` (or an overlay that
  names yours).
- A default storage class. On k3s that's `local-path`.
- For `deploy/clusters/contabo`: the CloudNativePG operator, Longhorn, the
  `traefik-public` ingress class and the `letsencrypt-prod` issuer.

## What maps to what

| Compose                                       | Kubernetes (`deploy/app`)                                        |
| --------------------------------------------- | ---------------------------------------------------------------- |
| `postgres`, `redis` + volumes                 | StatefulSets on the default storage class                        |
| `flask-init`                                  | initContainer on `backend` (migrate, sync-permissions, seed)     |
| `backend`, `celery-worker`, `celery-beat`     | Deployments (`backend.yaml`)                                     |
| `frontend`, `admin-frontend`, `sso-frontend`  | nginx Deployments, host names from ConfigMap `hubra-frontend`    |
| Traefik labels in the override file           | one `Ingress`, cert from cert-manager                            |
| `env_file: .env`                              | Secret `hubra-env` (`create-secrets.sh`)                          |
| `settings.yaml`                               | ConfigMap generated from the repo file; a change rolls the pods  |

Service names match the Compose names (`postgres`, `redis`, `backend`), so
hostnames in `.env` keep working.

## Setup

`deploy/app` serves `app`, `manage`, `sso` and `api.hubra.club`. Another
domain changes the hosts in `deploy/app/ingress.yaml` and the `hubra-frontend`
ConfigMap in `deploy/app/kustomization.yaml`, or uses an overlay like
`deploy/vollbuild-ch`.

1. **Images.** GitHub Actions (`.github/workflows/images.yml`) pushes
   `backend`, `frontend`, `admin-frontend`, `sso-frontend`, `haraka`,
   `zonemta` and `cert-watcher` to `ghcr.io/hubra-app/hubra/<image>` when a
   GitHub release is published (or when run by hand in the Actions tab). The frontend images hold no host names; they come from the
   `hubra-frontend` ConfigMap at container start.
2. **Secrets.** The repo is private, so are its packages. Create a GitHub
   token (classic) with `read:packages`, then on a machine with `.env`
   (`scripts/init-env.sh`, then set the production values, see
   `.env.example`) and cluster access run:
   ```sh
   GHCR_USER=<github login> GHCR_TOKEN=<token> deploy/create-secrets.sh
   ```
   `REDIS_URL` and `RATE_LIMIT_STORAGE` must use host `redis`, which the
   example already does. With CloudNativePG, run it with
   `POSTGRES_HOST=postgres-rw` (see below).
3. **Deploy** the directory you chose. With a GitOps tool, add this repo as a
   source (a read-only deploy key is enough) and sync that path. By hand:
   ```sh
   kubectl kustomize --load-restrictor LoadRestrictionsNone deploy/app | kubectl apply -f -
   ```
4. **First admin.** Sign up on the SSO host, then:
   ```sh
   kubectl -n hubra exec deploy/backend -- flask make-admin --email you@example.com
   ```
   Sign in again and create a club in the manager portal.

## The Contabo overlay

`deploy/clusters/contabo` runs `deploy/app` on a multi-node k3s cluster that
brings its own Traefik (`traefik-public`), cert-manager (`letsencrypt-prod`),
Longhorn and the [CloudNativePG](https://cloudnative-pg.io) operator. It sets
the hubra.club host names, resource requests and a preference for the `core`
nodes.

**Postgres.** The overlay replaces the single Postgres StatefulSet with a
CloudNativePG `Cluster` of three instances. Postgres streaming replication
keeps the copies in step, and each instance has its own `local-path` volume
on a different node, so Postgres never sits on Longhorn. If the primary's
node fails, the operator promotes a replica. The app connects through the
`postgres-rw` Service, which always points at the primary:

- `create-secrets.sh` with `POSTGRES_HOST=postgres-rw` writes that host into
  `DATABASE_URL` and creates the `hubra-postgres` secret the cluster takes
  its owner and password from.
- `bootstrap.initdb` in `postgres.yaml` names the database and owner. Keep
  them equal to `POSTGRES_DB` and `POSTGRES_USER` in `.env` (both `hubra` by
  default).

Redis and the Celery beat schedule stay on Longhorn: neither holds data that
needs more than that.

**Plugin marketplace.** The official plugin marketplace at
`plugins.hubra.club` is not on the cluster: GitHub Pages serves it from
hubra-app/hubra-plugins (`plugins/README.md`). Its Cloudflare record is a
CNAME to `hubra-app.github.io`.

**Behind Cloudflare.** Cloudflare -> Traefik -> backend is two
`X-Forwarded-For` hops, so the overlay sets `PROXY_FIX_X_FOR=2`. That is
only safe when Traefik trusts exactly Cloudflare's ranges on its HTTPS
entrypoint (`entryPoints.websecure.forwardedHeaders.trustedIPs`, list at
https://www.cloudflare.com/ips/). Otherwise Traefik drops the header,
every request looks like it came from Traefik, and all users share one
rate limit. Create the DNS records as DNS-only first, wait for the
certificate (`kubectl -n hubra get certificate`), then turn the proxy on
with SSL mode **Full (strict)**.

## Day to day

- **Deploy a new build:** publish a GitHub release (or run the Images
  workflow by hand), then pin `newTag` in `deploy/app/kustomization.yaml`
  (or your overlay) to the release (`1.2.3`) or the build tag
  (`sha-<commit>`) and push. `latest` follows the newest release, but
  Kubernetes doesn't notice a moved tag; with `latest`, run
  `kubectl -n hubra rollout restart deployment` after the workflow finishes.
  With Flux image automation, point the ImagePolicy at the sortable
  `main-<timestamp>-<commit>` tags that a manual run on `main` pushes
  (`pattern: '^main-(?P<ts>[0-9]{14})-[a-f0-9]+$'`, `extract: '$ts'`,
  numerical ascending); Flux then commits and rolls out each build itself.
- **Change settings:** edit `settings.yaml` and push.
- **Change secrets:** edit `.env`, re-run `create-secrets.sh`, then run
  `kubectl -n hubra rollout restart deployment`.
- **Logs:** `kubectl -n hubra logs deploy/backend -c flask-init` shows migrations.

## Moving data from Compose

Stop writes first (`docker compose stop backend celery-worker celery-beat`), then:

```sh
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" > hubra.dump
kubectl -n hubra exec -i postgres-0 -- sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' < hubra.dump
```

With CloudNativePG (`deploy/clusters/contabo`), restore into the primary
instead. The replicas follow on their own:

```sh
primary=$(kubectl -n hubra get cluster postgres -o jsonpath='{.status.currentPrimary}')
kubectl -n hubra exec -i "$primary" -c postgres -- \
  pg_restore -d hubra --role=hubra --clean --if-exists --no-owner < hubra.dump
```

Redis and the celery-beat schedule don't need moving. For mail data, see
`modules/mail/README.md`.

## Not ported yet

- The **CrowdSec and error-pages middlewares** lived in the external Traefik's
  file provider. Re-create them as Traefik `Middleware` objects and reference
  them from the Ingress. Keep OPTIONS preflights on `api.hubra.club`
  untouched, because Flask owns CORS.
- **Roundcube** isn't in either Compose file, so it isn't here either.
