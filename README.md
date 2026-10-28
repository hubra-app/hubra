# Hubra

A self-hosted club management platform with member management, finance, group
communication, events, polls, and an integrated self-hosted mail stack.

Hubra was previously called VollBuild COS (Club Operations Suite). VollBuild
is now only the name of the first club running it, which is why the default
deployment uses the `vollbuild.ch` hosts and seeds "VollBuild Makerspace" as
the club name.

## Architecture

The app is split across three subdomains of `vollbuild.ch`:

| Subdomain             | Served by     | Purpose                          |
| --------------------- | ------------- | -------------------------------- |
| `api.vollbuild.ch`    | Flask backend | REST API (JSON)                  |
| `cos.vollbuild.ch`    | Caddy + React | Tenant frontend SPA (members)    |
| `manage.vollbuild.ch` | Nginx + React | Admin portal SPA (superadmins)   |
| `sso.vollbuild.ch`    | Nginx + React | Centralized SSO login portal     |

An external Traefik terminates TLS and routes by Host header. JWT auth cookies
use `Domain=.vollbuild.ch` so they flow cross-subdomain. See
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
| **Deployment** | Docker Compose, or k3s + Flux (see docs/k3s.md)                     |

## Quick Start

```bash
git clone <repo-url>
cd club-management-suite
cp .env.example .env       # Edit with your secrets
docker compose up -d       # App stack only (default)
```

The self-hosted mail stack (WildDuck, Haraka, ZoneMTA) is opt-in. To run it
alongside the app:

```bash
docker compose -f docker-compose.yml -f modules/mail/docker-compose.mail.yml up -d
```

See [modules/mail/README.md](modules/mail/README.md) for mail prerequisites.

To run on k3s with Flux instead of Compose, see [docs/k3s.md](docs/k3s.md).

**Development mode:** See [docs/frontend.md](docs/frontend.md) and
[app/backend/API.md](app/backend/API.md).

## Testing

```bash
# Backend (756 tests)
cd app/backend
python -m pytest tests/ --ignore=tests/test_s11_backend_gaps.py

# Frontend
cd app/frontend
npm run build          # tsc + vite build
npm run lint           # ESLint

# E2E (requires running app)
cd app/frontend
npx playwright test
```

> `test_s11_backend_gaps.py` requires a running Redis instance and will hang
> if Redis is unavailable. The `--ignore` flag skips it when testing without
> Docker.

## Documentation

| Topic                                  | File                                                     |
| -------------------------------------- | -------------------------------------------------------- |
| Architecture & request flow            | [docs/architecture.md](docs/architecture.md)             |
| API endpoints, auth, permissions       | [docs/api-overview.md](docs/api-overview.md)             |
| Full API reference                     | [app/backend/API.md](app/backend/API.md)                 |
| Mail stack (WildDuck, Haraka, ZoneMTA) | [modules/mail/README.md](modules/mail/README.md)         |
| Running on k3s with Flux               | [docs/k3s.md](docs/k3s.md)                               |
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
├── deploy/                        # k3s manifests + Flux sync (docs/k3s.md)
├── .env.example                   # Environment variable template
├── AGENTS.md                      # AI agent instructions
├── app/
│   ├── backend/                   # Flask + Celery
│   │   ├── vollbuild/             # Application code
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
│       ├── k8s/                   # k3s manifests (Flux Kustomization `mail`)
│       ├── haraka/                # Inbound SMTP
│       ├── zonemta/               # Outbound SMTP
│       ├── certbot/               # TLS certificates
│       ├── cert-watcher/          # Hot-reload on renewal (Compose only)
│       └── scripts/               # validate-mail-config.py
├── docs/                          # All documentation
└── scripts/                       # Utility scripts (sync)
```
