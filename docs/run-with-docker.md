# Running Hubra with Docker Compose

One machine with Docker (Compose v2) is enough. The images come prebuilt from
GitHub Container Registry, built by `.github/workflows/images.yml` on every
push to `main`.

## 1. Get the code and log in to GHCR

```sh
git clone git@github.com:hubra-app/hubra.git
cd hubra
```

The repository is private, so its images are private too. Log in once with a
GitHub token that has the `read:packages` scope
(GitHub → Settings → Developer settings → Personal access tokens):

```sh
echo <token> | docker login ghcr.io -u <github-login> --password-stdin
```

Without registry access, build the images locally instead:
`docker compose build` (takes a few minutes).

## 2. Create `.env`

```sh
scripts/init-env.sh
```

This copies `.env.example` to `.env` and fills every secret with a random
value. The defaults run everything on localhost over plain HTTP. Keep
`BACKUP_ENCRYPTION_KEY` somewhere safe if you use backups.

## 3. Start

```sh
docker compose pull
docker compose up -d
docker compose ps          # flask-init should show "Exited (0)"
```

`flask-init` runs the database migrations and seed data, then the backend,
Celery worker and beat start.

| URL                     | What                     |
| ----------------------- | ------------------------ |
| http://localhost:8082   | Login and sign-up (SSO)  |
| http://localhost:8081   | Manager portal           |
| http://localhost:8080   | Club app                 |

Each frontend container forwards `/api/` to the backend, so no CORS or cookie
domain setup is needed locally.

## 4. First login and first club

1. Open http://localhost:8082, choose **Create account** and sign up.
2. Make that account the platform admin:
   ```sh
   docker compose exec backend flask make-admin --email you@example.com
   ```
3. Sign in again. You land in the manager portal (port 8081). Create a club
   under **Tenants** and give it an owner e-mail and password.
4. Optional modules (keys, guides, budgets, bank import, Discord) are off by
   default. Club admins switch them on in **Settings › Modules**, or:
   ```sh
   docker compose exec backend flask modules list --tenant <club-slug>
   docker compose exec backend flask modules enable finance.budgets --tenant <club-slug>
   ```

## Updating

```sh
git pull
docker compose pull
docker compose up -d
```

Pin a version with `HUBRA_VERSION` in `.env`: `latest` follows `main`,
`sha-<commit>` is one exact build, and release tags (`v1.2.3`) give `1.2.3`.

## Real host names (production)

The three apps and the API each get a host name behind a reverse proxy that
terminates TLS. Set in `.env`:

```sh
FRONTEND_BASE_URL=https://club.example.org
MANAGE_BASE_URL=https://manage.example.org
SSO_BASE_URL=https://sso.example.org
CORS_ORIGINS=https://club.example.org,https://manage.example.org,https://sso.example.org,https://join.example.org
JWT_COOKIE_SECURE=true
JWT_COOKIE_DOMAIN=.example.org
```

Then either:

- **Same-origin API (simplest):** point your proxy at the published ports
  (set `HUBRA_BIND=0.0.0.0` if the proxy runs on another machine) and keep
  `VITE_API_BASE=/api`. Each app reaches the API on its own host. Set
  `REAL_IP_FROM` to the proxy's address so rate limits see real client IPs.
- **Separate API host** (how the hosted Hubra runs): route `api.example.org` to the
  `backend` service and set `VITE_API_BASE=https://api.example.org/api`.
  `docker-compose.traefik.yml` does this with an external Traefik; enable it
  with `COMPOSE_FILE=docker-compose.yml:docker-compose.traefik.yml` in `.env`,
  and takes its host names from `HUBRA_APP_HOST`, `HUBRA_MANAGE_HOST`,
  `HUBRA_SSO_HOST`, `HUBRA_JOIN_HOST` and `HUBRA_API_HOST` (default
  `*.hubra.club`). The join host serves the SSO frontend too: people start a
  club there (`/start`) and find one to join (`/clubs`). Add its origin to
  `CORS_ORIGINS`.

The frontend images read these values when the container starts, so changing
them needs `docker compose up -d`, not a rebuild.

## Mail

Two options:

- **External provider (SMTP/IMAP):** fill in the `SMTP_*`, `IMAP_*` and
  `MAIL_*` values in `.env`.
- **Self-hosted stack** (WildDuck, Haraka, ZoneMTA): needs a public IP with
  port 25 open, DNS records and a Cloudflare token for certificates. See
  [modules/mail/README.md](../modules/mail/README.md), then:
  ```sh
  docker compose -f docker-compose.yml -f modules/mail/docker-compose.mail.yml up -d
  docker compose exec backend flask modules enable mail
  ```

## Testing a change

`scripts/smoke-test.sh` checks a running stack end to end: the apps answer,
they send their security headers, a club admin can sign in and the Celery
processes run. CI runs it on every pull request.

```sh
docker compose build && docker compose up -d
scripts/smoke-test.sh
```

For two clubs:
`docker compose exec backend flask provision-tenant --name "Club A" --slug club-a --admin-email a@example.org --admin-password '…'`.

## Useful commands

```sh
docker compose logs -f backend celery-worker
docker compose exec backend flask list-tenants
docker compose exec postgres pg_dump -U hubra -Fc hubra > hubra.dump
docker compose down            # stop (data stays in the volumes)
docker compose down -v         # stop and DELETE all data
```
