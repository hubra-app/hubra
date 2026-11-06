# Architecture

## Overview

```
                         Browser
                            │
                            ▼
              ┌───────────────────────────┐
              │ External Traefik or a     │  :443
              │ Kubernetes ingress (TLS,  │
              │ routing by host, CrowdSec)│
              └──┬───────────────┬────────┘
                 │               │
   app / manage / sso / join /   │ api.hubra.club
   support .hubra.club           │
                 ▼               ▼
        ┌─────────────────┐  ┌──────────────────────────────┐
        │ Frontend images │  │ Backend (Flask, gunicorn)    │
        │ nginx + React,  │  │ one process for all three    │
        │ CSP and headers │  │ API areas, or app / global / │
        │ set at start    │  │ platform as separate images  │
        └─────────────────┘  └───┬──────────┬──────────┬────┘
                                 │          │          │
                                 ▼          ▼          ▼
                          PostgreSQL     Redis      WildDuck API
                          (a schema     (Celery,    (mail stack,
                          per club)     limits)     optional)
                                 ▲          ▲
                                 │          │
                     Celery worker, beat, platform worker,
                     Discord gateway (profile), MCP server (profile)
```

The mail stack (MongoDB, WildDuck, Haraka, ZoneMTA, certbot) only runs when
it is switched on; see [modules/mail/README.md](../modules/mail/README.md).

## Request flow

1. **Browser → Traefik.** Traefik (or a Kubernetes ingress) terminates TLS and
   routes by host. CrowdSec middleware (`crowdsec@file`) sees every request.
2. **Traefik → a frontend image.** Each frontend (club app, manage, SSO/join,
   support) is an nginx image with the built files. Host names, the CSP and
   the other security headers are written when the container starts
   (`app/deploy/nginx/40-hubra-runtime.sh`), so one image fits every install.
3. **Traefik → backend.** With the production host names
   (`docker-compose.traefik.yml`, or a Kubernetes ingress), API calls go straight to Flask on
   `api.hubra.club`. There is one proxy hop, so ProxyFix uses `x_for=1`
   (`PROXY_FIX_X_FOR=2` only behind a CDN that Traefik trusts). The plain
   Compose stack on localhost has no API host: each frontend's nginx proxies
   `/api/` to the backend (`API_UPSTREAM`), so the app and the API share one
   origin.
4. **Flask ↔ PostgreSQL.** Shared data (accounts, clubs, platform settings)
   in `public`; each club's data in its own schema.
5. **Flask ↔ Redis.** Celery broker, rate limits, short-lived caches.
6. **Celery.** Mail, reminders, backups, plugin jobs and, with the mail stack,
   mailbox provisioning through the WildDuck API.

The API has three areas: `/api/v1/app` (the club app), `/api/v1/global`
(sign-in, account, public data) and `/api/v1/platform` (manage). How they run
as one or three backends is in [platform-backend.md](platform-backend.md).
Old paths (`/api/v1/members`, `/api/v1/manager/...`) still work and are
rewritten to the new ones (`hubra/core/api_areas.py`).

## Cross-origin auth

The frontends and the API are on different subdomains of one registrable
domain, so the browser treats their requests as same-site.

- **CORS** is owned by Flask. The allowlist is `CORS_ORIGINS` (no
  wildcards), and every CORS response carries `Vary: Origin`. Traefik must
  **not** add CORS headers: a second `Access-Control-Allow-Origin` makes
  browsers reject every response.
- **Preflight.** `OPTIONS` answers 200/204 with the CORS headers and skips
  auth, permissions and rate limits. CrowdSec and any error-page middleware
  must let `OPTIONS` through unchanged.
- **Cookies.** The JWT access and refresh tokens are HttpOnly cookies with
  `Domain=$JWT_COOKIE_DOMAIN` (`.hubra.club`), `SameSite=Lax`, `Secure` and
  `Path=/`. The path stays `/`: the frontends must be able to read the
  `csrf_*` cookies.
- **CSRF** uses the double-submit pattern: the readable `csrf_access_token`
  and `csrf_refresh_token` cookies go back as the `X-CSRF-TOKEN` header on
  every POST, PUT, PATCH and DELETE. `@hubra/api-client` does this for all
  frontends.
- **ProxyFix** is set to `x_for=1, x_proto=1, x_host=1`, so Flask sees the
  real client IP (rate limits), the HTTPS scheme (Secure cookies) and the API
  host.
- **Links in mails** are built from `FRONTEND_BASE_URL` and `SSO_BASE_URL`,
  never from `request.url_root`, which is the API host.

On plain-HTTP localhost, set `JWT_COOKIE_SECURE=false` and leave
`JWT_COOKIE_DOMAIN` empty (the `.env.example` defaults).

## Services

### App stack (`docker-compose.yml`)

| Container          | Image                | Role                                          |
| ------------------ | -------------------- | --------------------------------------------- |
| `frontend`         | `frontend`           | Club app, port 8080                           |
| `admin-frontend`   | `admin-frontend`     | Manage, port 8081                             |
| `sso-frontend`     | `sso-frontend`       | Sign-in, account and join, port 8082          |
| `support-frontend` | `support-frontend`   | support.hubra.club, port 8083                 |
| `backend`          | `backend`            | Flask API (gunicorn + ProxyFix)               |
| `flask-init`       | `backend`            | Migrations and seeds before the backend starts |
| `celery-worker`    | `backend`            | Background jobs                               |
| `celery-beat`      | `backend`            | Periodic job scheduler                        |
| `discord-gateway`  | `backend`            | Discord bot gateway (`discord` profile)       |
| `mcp`              | `mcp`                | Claude connector, port 8090 (`mcp` profile)   |
| `postgres`         | `postgres:16-alpine` | Database                                      |
| `redis`            | `redis:7-alpine`     | Celery broker, rate limits                    |

Images without a tag are `ghcr.io/hubra-app/hubra/<name>`.
`docker-compose.platform.yml` adds `platform-backend` and `platform-worker`
and runs the init step and beat on the platform image; see
[platform-backend.md](platform-backend.md).
`docker-compose.traefik.yml` adds the Traefik labels for the production
host names.

### Mail stack (`modules/mail/docker-compose.mail.yml`, opt-in)

| Container       | Image                           | Role                                   |
| --------------- | ------------------------------- | -------------------------------------- |
| `mongo`         | `mongo:7`                       | Mail data for WildDuck                 |
| `mailserver`    | `ghcr.io/zone-eu/wildduck`      | IMAP server                            |
| `haraka`        | `haraka`                        | Inbound SMTP                           |
| `zonemta`       | `zonemta`                       | Outbound SMTP                          |
| `certbot-init`  | `certbot/dns-cloudflare`        | First TLS certificate                  |
| `certbot-renew` | `certbot/dns-cloudflare`        | Certificate renewal every 12 h         |
| `cert-watcher`  | `cert-watcher`                  | Restarts mail services on a new certificate |
| `socket-proxy`  | `tecnativa/docker-socket-proxy` | Limited Docker socket for cert-watcher |

On Kubernetes the same images run from manifests kept in the cluster's own
repository; see [operator-guide.md](operator-guide.md#kubernetes).
