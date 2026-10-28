# Running on k3s with Flux

Flux watches this GitLab repo and keeps a single-node [k3s](https://k3s.io)
cluster in sync with it. To deploy, you push to `master`. Secrets stay out of
git and are created once with `deploy/create-secrets.sh`.

```
deploy/
├── flux/                     # what Flux syncs (flux bootstrap --path=deploy/flux)
│   ├── infrastructure.yaml   #   cert-manager, then issuer + Traefik tweaks
│   ├── app.yaml              #   deploy/app
│   └── mail.yaml             #   modules/mail/k8s (suspended = off)
├── infrastructure/           # cert-manager HelmRelease, Let's Encrypt issuer, k3s Traefik config
├── app/                      # the app stack (plain Kustomize)
└── create-secrets.sh         # .env -> Secret hubra-env (+ registry, Cloudflare)
modules/mail/k8s/             # the opt-in mail stack, see modules/mail/README.md
```

## What maps to what

| Compose                                       | k3s (`deploy/app`)                                               |
| --------------------------------------------- | ---------------------------------------------------------------- |
| `postgres`, `redis` + volumes                 | StatefulSets with `local-path` volumes                           |
| `flask-init`                                  | initContainer on `backend` (migrate, sync-permissions, seed)     |
| `backend`, `celery-worker`, `celery-beat`     | Deployments (`backend.yaml`)                                     |
| `frontend`, `admin-frontend`, `sso-frontend`  | nginx Deployments                                                |
| Traefik labels in the override file           | one `Ingress` on k3s's bundled Traefik, cert from cert-manager   |
| `env_file: .env`                              | Secret `hubra-env` (`create-secrets.sh`)                          |
| `settings.yaml`                               | ConfigMap generated from the repo file; a change rolls the pods  |

Service names match the Compose names (`postgres`, `redis`, `backend`), so
hostnames in `.env` keep working.

## Setup

1. **Install k3s and Flux CLI** on the node: `curl -sfL https://get.k3s.io | sh -`
   and `curl -s https://fluxcd.io/install.sh | sudo bash`.
2. **Images.** k3s can't build images, so GitLab CI pushes `backend`, `frontend`,
   `admin-frontend`, `sso-frontend`, `haraka` and `zonemta` to the project
   registry on `master`. Set the CI/CD variable
   `VITE_API_BASE=https://api.vollbuild.ch/api`, because the frontends bake it in.
   Replace `CHANGE-ME` in `deploy/app/kustomization.yaml` (and
   `modules/mail/k8s/kustomization.yaml`) with your GitLab group.
3. **Secrets.** Make a GitLab deploy token with `read_registry`, then on a
   machine with `.env` and cluster access run:
   ```sh
   REGISTRY_USER=<token user> REGISTRY_PASSWORD=<token> deploy/create-secrets.sh
   ```
   `REDIS_URL` and `RATE_LIMIT_STORAGE` in `.env` must use host `redis`, which
   they already do for Compose.
4. **Bootstrap Flux.** Use a GitLab personal access token with `api` scope:
   ```sh
   export GITLAB_TOKEN=<token>
   flux bootstrap gitlab --owner=<group> --repository=hubra \
     --branch=master --path=deploy/flux
   ```
   Flux commits its own manifests to `deploy/flux/flux-system/` and starts
   syncing. Check progress with `flux get kustomizations`.

**Ports 80/443.** k3s's Traefik binds them, which is where today's external
Traefik listens. Stop the external Traefik at cutover, because k3s's Traefik
replaces it.

## Day to day

- **Deploy a new build:** set `newTag` in `deploy/app/kustomization.yaml` to the
  commit SHA CI pushed, then push. Leave it at `latest` and run
  `kubectl -n hubra rollout restart deployment` if you prefer.
- **Change settings:** edit `settings.yaml` and push.
- **Change secrets:** edit `.env`, re-run `create-secrets.sh`, then run
  `kubectl -n hubra rollout restart deployment`.
- **Force a sync:** `flux reconcile kustomization app --with-source`.
- **Logs:** `kubectl -n hubra logs deploy/backend -c flask-init` shows migrations.

## Moving data from Compose

Stop writes first (`docker compose stop backend celery-worker celery-beat`), then:

```sh
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" > hubra.dump
kubectl -n hubra exec -i postgres-0 -- sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' < hubra.dump
```

Redis and the celery-beat schedule don't need moving. For mail data, see
`modules/mail/README.md`.

## Not ported yet

- The **CrowdSec and error-pages middlewares** lived in the external Traefik's
  file provider. Re-create them as Traefik `Middleware` objects and reference
  them from the Ingress. Keep OPTIONS preflights on `api.vollbuild.ch`
  untouched, because Flask owns CORS.
- **Roundcube** isn't in either Compose file, so it isn't here either.
