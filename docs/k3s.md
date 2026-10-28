# Running on k3s with Flux

Flux watches the GitHub repo (`hubra-app/hubra`) and keeps a single-node
[k3s](https://k3s.io) cluster in sync with it. To deploy, you push to `main`. Secrets stay out of
git and are created once with `deploy/create-secrets.sh`.

```
deploy/
├── flux/                     # what Flux syncs (flux bootstrap --path=deploy/flux)
│   ├── infrastructure.yaml   #   cert-manager, then issuer + Traefik tweaks
│   ├── app.yaml              #   deploy/app
│   ├── mail.yaml             #   modules/mail/k8s (suspended = off)
│   └── image-automation.yaml.example  # rename to switch on image automation
├── flux-image-automation/    # optional: Flux bumps image tags on new builds
├── infrastructure/           # cert-manager HelmRelease, Let's Encrypt issuer, k3s Traefik config
├── app/                      # the app stack (plain Kustomize)
└── create-secrets.sh         # .env -> Secret hubra-env (+ GHCR pull secret, Cloudflare)
modules/mail/k8s/             # the opt-in mail stack, see modules/mail/README.md
```

## What maps to what

| Compose                                       | k3s (`deploy/app`)                                               |
| --------------------------------------------- | ---------------------------------------------------------------- |
| `postgres`, `redis` + volumes                 | StatefulSets with `local-path` volumes                           |
| `flask-init`                                  | initContainer on `backend` (migrate, sync-permissions, seed)     |
| `backend`, `celery-worker`, `celery-beat`     | Deployments (`backend.yaml`)                                     |
| `frontend`, `admin-frontend`, `sso-frontend`  | nginx Deployments, host names from ConfigMap `hubra-frontend`    |
| Traefik labels in the override file           | one `Ingress` on k3s's bundled Traefik, cert from cert-manager   |
| `env_file: .env`                              | Secret `hubra-env` (`create-secrets.sh`)                          |
| `settings.yaml`                               | ConfigMap generated from the repo file; a change rolls the pods  |

Service names match the Compose names (`postgres`, `redis`, `backend`), so
hostnames in `.env` keep working.

## Setup

For one club without the manager and SSO portals, use the overlay
`deploy/single-club` instead of `deploy/app` (see
[single-club.md](single-club.md)). The steps below are the same.

`deploy/app` serves `app`, `manage`, `sso` and `api.hubra.club`. Another
domain changes the hosts in `deploy/app/ingress.yaml` and the `hubra-frontend`
ConfigMap in `deploy/app/kustomization.yaml`, or uses an overlay like
`deploy/vollbuild-ch`, which keeps the existing `vollbuild.ch` server on its
old hosts (`path: ./deploy/vollbuild-ch` in `deploy/flux/app.yaml`).

1. **Install k3s and the Flux CLI** on the node:
   ```sh
   curl -sfL https://get.k3s.io | sh -
   curl -s https://fluxcd.io/install.sh | sudo bash
   export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
   ```
2. **Images.** k3s can't build images. GitHub Actions
   (`.github/workflows/images.yml`) pushes `backend`, `frontend`,
   `admin-frontend`, `sso-frontend`, `haraka`, `zonemta` and `cert-watcher` to
   `ghcr.io/hubra-app/hubra/<image>` on every push to `main`. Check the
   **Actions** tab after the first push. The frontend images hold no host
   names; set yours in the `hubra-frontend` ConfigMap in
   `deploy/app/kustomization.yaml` and in `deploy/app/ingress.yaml`.
3. **Secrets.** The repo is private, so are its packages. Create a GitHub
   token (classic) with `read:packages`, then on a machine with `.env`
   (`scripts/init-env.sh`, then set the production values, see
   `.env.example`) and cluster access run:
   ```sh
   GHCR_USER=<github login> GHCR_TOKEN=<token> deploy/create-secrets.sh
   ```
   `REDIS_URL` and `RATE_LIMIT_STORAGE` must use host `redis`, which the
   example already does.
4. **Bootstrap Flux** with a GitHub token that can administer the repo
   (classic: `repo`; fine-grained: Administration + Contents read/write):
   ```sh
   export GITHUB_TOKEN=<token>
   flux bootstrap github --owner=hubra-app --repository=hubra \
     --branch=main --path=deploy/flux
   ```
   Flux adds a deploy key to the repo, commits its own manifests to
   `deploy/flux/flux-system/` and starts syncing. Watch it with
   `flux get kustomizations --watch`. `git pull` afterwards so your checkout
   has Flux's commit.
5. **First admin.** Sign up on the SSO host, then:
   ```sh
   kubectl -n hubra exec deploy/backend -- flask make-admin --email you@example.com
   ```
   Sign in again and create a club in the manager portal.

**Ports 80/443.** k3s's Traefik binds them, which is where today's external
Traefik listens. Stop the external Traefik at cutover, because k3s's Traefik
replaces it.

## Day to day

- **Deploy a new build:** `latest` follows `main`, but Kubernetes doesn't
  notice a moved tag. Run `kubectl -n hubra rollout restart deployment` after
  the Images workflow finishes, or pin `newTag` in
  `deploy/app/kustomization.yaml` to a build tag (`sha-<commit>`) or a
  release (`1.2.3`) and push.
- **Automatic roll-outs (optional):** Flux image automation picks up every
  new `main` build and commits the tag for you. Bootstrap with
  `--components-extra=image-reflector-controller,image-automation-controller --read-write-key`,
  create the `ghcr-pull` secret in `flux-system` as well, and rename
  `deploy/flux/image-automation.yaml.example` to `image-automation.yaml`.
  Details are at the top of `deploy/flux-image-automation/image-automation.yaml`.
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
  them from the Ingress. Keep OPTIONS preflights on `api.hubra.club`
  untouched, because Flask owns CORS.
- **Roundcube** isn't in either Compose file, so it isn't here either.
