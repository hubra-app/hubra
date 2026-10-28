# Architecture

## Overview

```
                    ┌──────────────────────────┐
                    │  External Traefik         │ :443/:80
                    │  (TLS termination,        │
                    │   routing, CrowdSec)      │
                    └──────┬───────────┬────────┘
                           │           │
               Host(app.hubra.club)  Host(api.hubra.club)
                           │           │
                           ▼           ▼
                    ┌──────────────┐  ┌──────────────┐
                    │   Caddy 2    │  │   Backend    │
                    │  (frontend   │  │  Flask API   │
                    │   + headers) │  │  :5000       │
                    │   :80        │  │              │
                    └──────┬───────┘  └──────┬───────┘
                           │                 │
                           ▼                 │
                    ┌──────────────┐         │
                    │   Frontend   │         │
                    │  React SPA   │         │
                    │  :80         │         │
                    └──────────────┘         │
                                             │
                              ┌──────────────┼──────────────┐
                              │              │              │
                              ▼              ▼              ▼
                      ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
                      │  PostgreSQL  │ │    Redis     │ │   MongoDB    │
                      │  (app data)  │ │ (queue+rate) │ │  (mail data) │
                      └──────────────┘ └──────────────┘ └──────┬───────┘
                                                                       │
                      ┌─────────────────────────────────┼───────────────────┐
                      │                                 │                   │
                      ▼                                 ▼                   ▼
              ┌──────────────┐                  ┌──────────────┐  ┌──────────────┐
              │   Haraka     │◄── port 25 ──────│  WildDuck    │  │   ZoneMTA    │
              │ (inbound SMTP)│                 │ (IMAP server) │  │(outbound SMTP)│
              └──────────────┘                  └──────────────┘  └──────────────┘
                                                                       │
                                                             port 465/587
                                                                       │
                                                                       ▼
                                                                 Internet
```

> The lower half of the diagram (MongoDB, Haraka, WildDuck, ZoneMTA) only
> applies when the optional mail stack is running. See
> [modules/mail/README.md](../modules/mail/README.md) for how to enable it.

## Request flow

1. **Browser → Traefik** — External Traefik terminates TLS and routes by Host
   header. CrowdSec middleware (`crowdsec@file`) inspects all requests.
2. **Traefik → Caddy** (`app.hubra.club`) — Frontend HTML/JS served by Caddy
   → React SPA. Caddy adds CSP, Permissions-Policy, and other security headers.
3. **Traefik → Backend** (`api.hubra.club`) — API requests go directly to
   Flask (no Caddy proxy). One proxy hop; ProxyFix `x_for=1`.
4. **Flask ↔ PostgreSQL** — Member data, groups, finance, settings, audit log.
5. **Flask ↔ Redis** — Rate limiting storage, Celery broker.
6. **Celery tasks → WildDuck API** — Async mailbox/alias provisioning, password
   sync, retention cleanup (only when mail stack is enabled).

## Cross-origin auth

The API and frontend are on different subdomains. See
[SUBDOMAIN_MIGRATION.md](SUBDOMAIN_MIGRATION.md) for the full setup.

- **CORS** — Owned by Flask (single source of truth). The external Traefik must
  NOT add CORS headers (duplicate `Access-Control-Allow-Origin` breaks
  browsers). Allowlist via `CORS_ORIGINS`, no wildcards, `Vary: Origin` on all
  CORS responses.
- **Cookies** — JWT access/refresh tokens in HttpOnly cookies with
  `Domain=.hubra.club`, `SameSite=Lax`, `Secure`. CSRF double-submit via
  readable `csrf_*` cookies + `X-CSRF-TOKEN` header.
- **Preflight** — `OPTIONS` returns 200/204 with CORS headers, exempt from auth,
  RBAC, and rate limiting. CrowdSec (Traefik) must also pass OPTIONS through.
- **ProxyFix** — `x_for=1, x_proto=1, x_host=1` so the app sees the real client
  IP (CrowdSec/rate-limit attribution), HTTPS scheme (Secure cookies), and
  `api.hubra.club` host.
- **Email links** — `FRONTEND_BASE_URL` (e.g. `https://app.hubra.club`) is
  used for password-reset and email-verification links, not `request.url_root`
  (which resolves to the API host).

## Services

### App stack (`docker-compose.yml`)

| Container       | Image                      | Role                                      |
| --------------- | -------------------------- | ----------------------------------------- |
| `caddy`         | `caddy:2.8-alpine`         | Frontend reverse proxy + security headers |
| `frontend`      | Build from `app/frontend/` | React SPA served via nginx                |
| `backend`       | Build from `app/backend/`  | Flask API (gunicorn + ProxyFix)           |
| `flask-init`    | Build from `app/backend/`  | Runs migrations + seed on first start     |
| `celery-worker` | Build from `app/backend/`  | Async task worker                         |
| `celery-beat`   | Build from `app/backend/`  | Periodic task scheduler                   |
| `postgres`      | `postgres:16-alpine`       | Primary app database                      |
| `redis`         | `redis:7-alpine`           | Queue broker, rate-limit storage          |

### Mail stack (`docker-compose.mail.yml` — opt-in)

| Container       | Image                           | Role                                   |
| --------------- | ------------------------------- | -------------------------------------- |
| `mongo`         | `mongo:7`                       | Mail data for WildDuck                 |
| `mailserver`    | `ghcr.io/zone-eu/wildduck`      | IMAP mail server                       |
| `haraka`        | Build from `mail/haraka/`       | Inbound SMTP                           |
| `zonemta`       | Build from `mail/zonemta/`      | Outbound SMTP                          |
| `certbot-init`  | `certbot/dns-cloudflare`        | One-shot TLS certificate issuance      |
| `certbot-renew` | `certbot/dns-cloudflare`        | Cert renewal every 12h                 |
| `cert-watcher`  | Build from `mail/cert-watcher/` | Restarts mail services on cert change  |
| `socket-proxy`  | `tecnativa/docker-socket-proxy` | Secured Docker socket for cert-watcher |
