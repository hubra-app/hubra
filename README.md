# Hubra

A self-hosted club management platform with member management, finance, group
communication, events, polls, and an integrated self-hosted mail stack.

Hubra was previously called VollBuild COS (Club Operations Suite). VollBuild
is now only the name of the first club running it, which is why a fresh
install still seeds "VollBuild Makerspace" as the club name. The default host
names are under `hubra.club`; the existing `vollbuild.ch` server keeps its
hosts through `.env` (Compose) or the `deploy/vollbuild-ch` overlay (k3s).

## Architecture

The app is split across four subdomains of `hubra.club`:

| Subdomain           | Served by     | Purpose                          |
| ------------------- | ------------- | -------------------------------- |
| `api.hubra.club`    | Flask backend | REST API (JSON)                  |
| `app.hubra.club`    | Caddy + React | Tenant frontend SPA (members)    |
| `manage.hubra.club` | Nginx + React | Admin portal SPA (superadmins)   |
| `sso.hubra.club`    | Nginx + React | Centralized SSO login portal     |

An external Traefik terminates TLS and routes by Host header. JWT auth cookies
use `Domain=.hubra.club` so they flow cross-subdomain. See
[docs/SUBDOMAIN_MIGRATION.md](docs/SUBDOMAIN_MIGRATION.md) for the full
cross-origin auth setup (CORS, CSRF, cookie attributes, ProxyFix).

## Tech Stack

| Layer          | Technology                                                          |
| -------------- | ------------------------------------------------------------------- |
| **Frontend**   | React 19, TypeScript 6, Vite 8, Mantine 7, TanStack Query 5         |
| **Backend**    | Flask 3, Python 3.13, SQLAlchemy, Marshmallow                       |
| **Database**   | PostgreSQL 16, MongoDB 7 (mail), Redis 7                            |
| **Background** | Celery 5 + Redis                                                    |
| **Mail**       | WildDuck (IMAP), Haraka (inbound SMTP), ZoneMTA (outbound SMTP)     |
| **Edge**       | External Traefik (TLS, routing, CrowdSec) + Caddy 2 (frontend only) |
| **Deployment** | Docker Compose, or Kubernetes/k3s manifests (see docs/k3s.md)       |

## Quick Start

```bash
git clone git@github.com:hubra-app/hubra.git
cd hubra
scripts/init-env.sh        # .env with fresh secrets, localhost defaults
docker compose pull        # images from GHCR (or: docker compose build)
docker compose up -d
```

Then open http://localhost:8082, sign up, and make yourself the platform admin
with `docker compose exec backend flask make-admin --email you@example.com`.
The full walkthrough, production host names and mail are in
[docs/run-with-docker.md](docs/run-with-docker.md).

To run on Kubernetes (k3s) instead, see [docs/k3s.md](docs/k3s.md). The images
are built by GitHub Actions (`.github/workflows/images.yml`) and pushed to
`ghcr.io/hubra-app/hubra/*`.

**Development mode:** See [docs/frontend.md](docs/frontend.md) and
[app/backend/API.md](app/backend/API.md).

## Testing

```bash
# Backend
cd app/backend
python -m pytest tests/

# Frontend
cd app/frontend
npm run build          # tsc + vite build
npm run lint           # ESLint

# E2E (requires running app)
cd app/frontend
npx playwright test
```

## Documentation

| Topic                                  | File                                                     |
| -------------------------------------- | -------------------------------------------------------- |
| Architecture & request flow            | [docs/architecture.md](docs/architecture.md)             |
| API endpoints, auth, permissions       | [docs/api-overview.md](docs/api-overview.md)             |
| Full API reference                     | [app/backend/API.md](app/backend/API.md)                 |
| Mail stack (WildDuck, Haraka, ZoneMTA) | [modules/mail/README.md](modules/mail/README.md)         |
| Running on Kubernetes (k3s)            | [docs/k3s.md](docs/k3s.md)                               |
| Frontend stack & structure             | [docs/frontend.md](docs/frontend.md)                     |
| Environment & settings config          | [docs/configuration.md](docs/configuration.md)           |
| Subdomain migration (CORS, cookies)    | [docs/SUBDOMAIN_MIGRATION.md](docs/SUBDOMAIN_MIGRATION.md) |
| Disaster recovery runbook              | [docs/disaster-recovery.md](docs/disaster-recovery.md)   |
| Frontend review issues (snapshot)      | [docs/frontend_issues.md](docs/frontend_issues.md)       |
| Project management & milestones        | [docs/project-management.md](docs/project-management.md) |
| Backend changelog                      | [app/backend/CHANGELOG.md](app/backend/CHANGELOG.md)     |

## Project structure

```
├── docker-compose.yml             # App stack (default)
├── docker-compose.override.yaml   # Production routing + env overrides
├── settings.yaml                  # Deployment-time feature flags & limits
├── deploy/                        # Kubernetes manifests (docs/k3s.md)
├── .env.example                   # Environment variable template
├── AGENTS.md                      # AI agent instructions
├── app/
│   ├── backend/                   # Flask + Celery
│   │   ├── hubra/             # Application code
│   │   ├── tests/                 # 756 tests (blueprint-organized)
│   │   ├── migrations/            # Alembic migrations (flask db migrate)
│   │   ├── API.md                 # Full API reference
│   │   ├── CHANGELOG.md           # Keep a Changelog
│   │   ├── BUILD.md               # Build instructions
│   │   └── wsgi.py                # Gunicorn entry point (ProxyFix)
│   ├── frontend/                  # React SPA
│   │   ├── src/
│   │   │   ├── api/               # API client modules
│   │   │   ├── components/        # Shared UI (Mantine-based)
│   │   │   ├── screens/           # Route-level pages
│   │   │   ├── locales/           # i18n
│   │   │   └── types/             # TypeScript interfaces
│   │   └── e2e/                   # Playwright E2E tests
│   └── deploy/
│       └── Caddyfile              # Frontend proxy + security headers
├── modules/
│   └── mail/                      # Opt-in self-hosted mail stack, self-contained
│       ├── docker-compose.mail.yml  # Compose add-on (opt-in via -f)
│       ├── k8s/                   # Kubernetes manifests (opt-in)
│       ├── haraka/                # Inbound SMTP
│       ├── zonemta/               # Outbound SMTP
│       ├── certbot/               # TLS certificates
│       ├── cert-watcher/          # Hot-reload on renewal (Compose only)
│       └── scripts/               # validate-mail-config.py
├── docs/                          # All documentation
└── scripts/                       # Utility scripts (sync)
```

## License

Copyright (c) 2026 Mike Keller. All rights reserved.

The source is public so it can be read, but Hubra is not open source.
Running, self-hosting, modifying or redistributing it needs written
permission; see [LICENSE](LICENSE).
