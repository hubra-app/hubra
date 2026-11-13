# Hubra

[![CI](https://github.com/hubra-app/hubra/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/hubra-app/hubra/actions/workflows/ci.yml?query=branch%3Amain) [![Images](https://github.com/hubra-app/hubra/actions/workflows/images.yml/badge.svg)](https://github.com/hubra-app/hubra/actions/workflows/images.yml) [![License: all rights reserved](https://img.shields.io/badge/license-all%20rights%20reserved-lightgrey)](LICENSE) [![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-bitsandbricks-ffdd00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/bitsandbricks)

A self-hosted club management platform with member management, finance,
groups, events and trainings, polls, a member portal with sign-in through one
shared account, plugins from a signed Marketplace, a Discord bot, and an
optional self-hosted mail stack.

Hubra was previously called VollBuild COS (Club Operations Suite). VollBuild
is now only the name of the first club running it, which is why a fresh
install still seeds "VollBuild Makerspace" as the club name. The default host
names are under `hubra.club`; the existing `vollbuild.ch` server keeps its
hosts through `.env`.

## Architecture

Every part runs on its own host under `hubra.club`:

| Host                 | Served by                   | Purpose                                                        |
| -------------------- | --------------------------- | -------------------------------------------------------------- |
| `api.hubra.club`     | Flask backend               | REST API (JSON)                                                |
| `app.hubra.club`     | Nginx + React               | Club app (members and club admins)                             |
| `manage.hubra.club`  | Nginx + React               | Manage, the platform admin portal                              |
| `sso.hubra.club`     | Nginx + React               | Sign-in, sign-up and the person's account                      |
| `join.hubra.club`    | the SSO frontend again      | Start a club, find one and ask to join                         |
| `support.hubra.club` | Nginx + React               | Help, roadmap with voting, status, reports and ideas ([docs](docs/support-site.md)) |
| `mcp.hubra.club`     | MCP server                  | Claude connector, read-only, with an API token ([docs](docs/mcp.md)) |
| `plugins.hubra.club` | GitHub Pages                | The plugin Marketplace ([hubra-plugins](https://github.com/hubra-app/hubra-plugins)) |

The API has three areas, `/api/v1/app` (the club app), `/api/v1/global`
(sign-in, account, public data) and `/api/v1/platform` (manage). They can run
as one backend (the Compose default) or as three deployments with their own
images, so a platform change does not restart sign-in or the club app; see
[docs/platform-backend.md](docs/platform-backend.md). Celery runs the
background jobs, and with the `discord` profile a gateway process runs the
Discord bot ([docs/discord.md](docs/discord.md)).

An external Traefik (or a Kubernetes ingress) terminates TLS and routes by Host
header. JWT auth cookies use `Domain=.hubra.club` so they flow
cross-subdomain. See [docs/architecture.md](docs/architecture.md) for the
cross-origin auth setup (CORS, CSRF, cookie attributes, ProxyFix).

## Tech Stack

| Layer          | Technology                                                                 |
| -------------- | -------------------------------------------------------------------------- |
| **Frontend**   | React 19, TypeScript 6, Vite 8, Mantine 9, TanStack Query 5; shared `@hubra/ui` and `@hubra/api-client` in `packages/` |
| **Backend**    | Flask 3, Python 3.13, SQLAlchemy, Marshmallow                              |
| **Database**   | PostgreSQL (16 in Compose, 18 in the release checks; backups handle 16 to 18), Redis 7, MongoDB 7 (mail only) |
| **Background** | Celery 5 + Redis (worker, beat, platform worker when split)                |
| **Mail**       | WildDuck (IMAP), Haraka (inbound SMTP), ZoneMTA (outbound SMTP), opt-in   |
| **Edge**       | External Traefik (TLS, routing, CrowdSec) + Nginx in each frontend image  |
| **Deployment** | Images on GHCR; Docker Compose here, Kubernetes manifests in the cluster's own repo |

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
Manage is on port 8081, the club app on 8080 and the support site on 8083.
The full walkthrough, production host names (`docker-compose.traefik.yml`),
the split platform backend (`docker-compose.platform.yml`) and mail are in
[docs/run-with-docker.md](docs/run-with-docker.md).

This repository builds the images; it holds no Kubernetes manifests. A
cluster runs the same images with the same environment variables from its own
GitOps repository ([docs/operator-guide.md](docs/operator-guide.md#kubernetes)).

**Development mode:** See [docs/frontend.md](docs/frontend.md) and
[app/backend/API.md](app/backend/API.md).

## Images, CI and releases

The images are built by GitHub Actions (`.github/workflows/images.yml`) and
pushed to `ghcr.io/hubra-app/hubra/*`: `backend` (every role, for Compose),
`app-backend`, `global-backend` and `platform-backend` (one role each, see
[docs/platform-backend.md](docs/platform-backend.md)), `frontend`, `admin-frontend`,
`sso-frontend`, `support-frontend`, `mcp`, and for mail `haraka`, `zonemta`
and `cert-watcher`. They are built only for a release (Flux follows version
releases), and only images whose files changed are rebuilt; the others get
the new tags on the same digest. A release starts with a `v*` tag push, like
the plugins: tests, images, a maintainer's approval, then the signed images
and the GitHub release ([docs/releases.md](docs/releases.md)).

Pull requests run lint and tests only for the parts they touch, and the
browser tests when a change reaches what the browser sees; the full checks
(Postgres, audits, image builds) run on `release/*` and before every image
build. `main` and the released `v*` tags are mirrored to GitLab, which runs the checks
again and creates the GitLab Releases.

| Topic                                     | File                                                 |
| ----------------------------------------- | ---------------------------------------------------- |
| Cutting, approving and verifying a release | [docs/releases.md](docs/releases.md)                |
| Workflows and branch protection           | [docs/ci.md](docs/ci.md)                             |
| Versions, tags and which images to build  | [docs/release-guidelines.md](docs/release-guidelines.md) |
| GitLab mirror and releases                | [docs/gitlab.md](docs/gitlab.md)                     |

## Testing

```bash
# Backend (pip install pytest pytest-flask pytest-xdist)
cd app/backend
python -m pytest -n auto        # SQLite, as on every pull request
# On Postgres, as the release checks do (one database per worker is created):
TEST_DATABASE_URL=postgresql://hubra:hubra@localhost/hubra_test python -m pytest -n auto

# Frontend (the same in admin-frontend, sso-frontend and support-frontend)
cd app/frontend
npm test               # Vitest unit tests
npm run build          # tsc + vite build
npm run lint           # ESLint

# Browser tests (Playwright, against a running Compose stack)
cd app/frontend
npx playwright test
```

How CI starts the stack for the browser tests is in [docs/ci.md](docs/ci.md).

## Plugins

The official plugins live in their own repositories and are published, signed,
on the [Marketplace](https://plugins.hubra.club). Each club switches on the
ones it needs under **Settings › Modules**. The versions below are the latest
GitHub release of each plugin.

| Plugin | What it does | Version |
| --- | --- | --- |
| [Assistant](https://github.com/hubra-app/hubra-plugin-assistant) | Writing help for the board: drafts of posts, invitations, reminders and minutes with Claude, using the club's own API key | [1.0.0](https://github.com/hubra-app/hubra-plugin-assistant/releases/tag/v1.0.0) |
| [Bank file import](https://github.com/hubra-app/hubra-plugin-bank-import) | Import camt.053, camt.054, MT940 and CSV statements and match payments to invoices | [1.2.0](https://github.com/hubra-app/hubra-plugin-bank-import/releases/tag/v1.2.0) |
| [Board](https://github.com/hubra-app/hubra-plugin-board) | Board tasks per function, a year planner, contracts with notice reminders, and the general meeting | [1.0.0](https://github.com/hubra-app/hubra-plugin-board/releases/tag/v1.0.0) |
| [Booking](https://github.com/hubra-app/hubra-plugin-booking) | Rooms and equipment on a calendar, with approvals and fees on the member's invoice | [1.0.0](https://github.com/hubra-app/hubra-plugin-booking/releases/tag/v1.0.0) |
| [Budgets](https://github.com/hubra-app/hubra-plugin-budgets) | A yearly budget per category with an owner, compared with what was booked | [1.3.0](https://github.com/hubra-app/hubra-plugin-budgets/releases/tag/v1.3.0) |
| [Codes](https://github.com/hubra-app/hubra-plugin-codes) | Door codes, lock combinations and passcodes, encrypted with the club's key | [2.0.1](https://github.com/hubra-app/hubra-plugin-codes/releases/tag/v2.0.1) |
| [Community](https://github.com/hubra-app/hubra-plugin-community) | Photo albums, a skills and lending directory, an idea box, a welcome checklist and jubilees | [1.0.0](https://github.com/hubra-app/hubra-plugin-community/releases/tag/v1.0.0) |
| [Discord](https://github.com/hubra-app/hubra-plugin-discord) | The Hubra bot: announcements, roles, group channels, events, polls and reminders | [2.7.1](https://github.com/hubra-app/hubra-plugin-discord/releases/tag/v2.7.1) |
| [Documents](https://github.com/hubra-app/hubra-plugin-documents) | The club's document library: folders, uploads and access per role or group | [1.0.0](https://github.com/hubra-app/hubra-plugin-documents/releases/tag/v1.0.0) |
| [Forms](https://github.com/hubra-app/hubra-plugin-forms) | Forms and surveys, with answers as a summary, a table or a CSV | [1.0.0](https://github.com/hubra-app/hubra-plugin-forms/releases/tag/v1.0.0) |
| [Guides](https://github.com/hubra-app/hubra-plugin-guides) | A usage guide per machine or tool, shown on the inventory item | [1.3.1](https://github.com/hubra-app/hubra-plugin-guides/releases/tag/v1.3.1) |
| [Inventory](https://github.com/hubra-app/hubra-plugin-inventory) | Tools, machines and materials, with owners, checkouts and inductions | [2.1.0](https://github.com/hubra-app/hubra-plugin-inventory/releases/tag/v2.1.0) |
| [Kasse](https://github.com/hubra-app/hubra-plugin-kasse) | Expense claims, a drinks and materials tab with QR codes, and collective orders | [1.0.0](https://github.com/hubra-app/hubra-plugin-kasse/releases/tag/v1.0.0) |
| [Keys](https://github.com/hubra-app/hubra-plugin-keys) | Who holds which key, card or fob, with a handover log | [1.2.1](https://github.com/hubra-app/hubra-plugin-keys/releases/tag/v1.2.1) |
| [Letters](https://github.com/hubra-app/hubra-plugin-letters) | Serial letters as one PDF for window envelopes, or printed and posted by Pingen | [1.0.0](https://github.com/hubra-app/hubra-plugin-letters/releases/tag/v1.0.0) |
| [Messengers](https://github.com/hubra-app/hubra-plugin-messengers) | Announcements and reminders in the club's Telegram, Signal or Matrix group | [1.0.0](https://github.com/hubra-app/hubra-plugin-messengers/releases/tag/v1.0.0) |
| [Online payments](https://github.com/hubra-app/hubra-plugin-payments) | Members pay invoices by card or TWINT through the club's own Stripe account | [1.0.0](https://github.com/hubra-app/hubra-plugin-payments/releases/tag/v1.0.0) |
| [Shared inbox (IMAP)](https://github.com/hubra-app/hubra-plugin-imap-inbox) | Read club mailboxes hosted anywhere inside Hubra | [1.1.0](https://github.com/hubra-app/hubra-plugin-imap-inbox/releases/tag/v1.1.0) |
| [Supporters](https://github.com/hubra-app/hubra-plugin-supporters) | Sponsor packages and invoices, fundraising goals, donations and pledges | [1.0.0](https://github.com/hubra-app/hubra-plugin-supporters/releases/tag/v1.0.0) |
| [Teams](https://github.com/hubra-app/hubra-plugin-teams) | Match days for team sports: fixtures, availability, line-ups and carpooling | [1.0.0](https://github.com/hubra-app/hubra-plugin-teams/releases/tag/v1.0.0) |

When a plugin is released or a new one added, follow
[docs/plugin-releases.md](docs/plugin-releases.md) so this table, the
Marketplace README and the hubra.club Modules page stay current.

## Documentation

| Topic                                  | File                                                     |
| -------------------------------------- | -------------------------------------------------------- |
| Operators: install, upgrade, keys, backups | [docs/operator-guide.md](docs/operator-guide.md)     |
| Club owners and admins                 | [docs/club-admin-guide.md](docs/club-admin-guide.md)     |
| Run with Docker Compose                | [docs/run-with-docker.md](docs/run-with-docker.md)       |
| Split backends (app, global, platform) | [docs/platform-backend.md](docs/platform-backend.md)     |
| More than one replica                  | [docs/scaling.md](docs/scaling.md)                       |
| Disaster recovery runbook              | [docs/disaster-recovery.md](docs/disaster-recovery.md)   |
| Environment & settings config          | [docs/configuration.md](docs/configuration.md)           |
| Early access per club (feature flags)  | [docs/feature-flags.md](docs/feature-flags.md)           |
| Architecture & request flow            | [docs/architecture.md](docs/architecture.md)             |
| API endpoints, auth, permissions       | [docs/api-overview.md](docs/api-overview.md)             |
| Full API reference                     | [app/backend/API.md](app/backend/API.md)                 |
| API tokens                             | [docs/api-tokens.md](docs/api-tokens.md)                 |
| Public API (pricing, plugins)          | [docs/public-api.md](docs/public-api.md)                 |
| Claude connector (MCP server)          | [docs/mcp.md](docs/mcp.md)                               |
| Discord bot                            | [docs/discord.md](docs/discord.md)                       |
| Notifications and quiet hours          | [docs/notifications.md](docs/notifications.md)           |
| Member badge in Google Wallet          | [docs/google-wallet.md](docs/google-wallet.md)           |
| Support site                           | [docs/support-site.md](docs/support-site.md)             |
| Mail stack (WildDuck, Haraka, ZoneMTA) | [modules/mail/README.md](modules/mail/README.md)         |
| Plugins and extension areas            | [docs/plugins.md](docs/plugins.md), [plugins/README.md](plugins/README.md) |
| Plugin release checklist               | [docs/plugin-releases.md](docs/plugin-releases.md)       |
| Frontend stack & structure             | [docs/frontend.md](docs/frontend.md)                     |
| Design spec (all frontends)            | [docs/design-spec.md](docs/design-spec.md)               |
| List search, filter and sort           | [docs/table-controls.md](docs/table-controls.md)         |
| Brand assets                           | [brand/README.md](brand/README.md)                       |
| CI, releases, GitLab                   | [docs/ci.md](docs/ci.md), [docs/release-guidelines.md](docs/release-guidelines.md), [docs/gitlab.md](docs/gitlab.md) |
| Changelog (English, German)            | [app/backend/CHANGELOG.md](app/backend/CHANGELOG.md), [app/backend/CHANGELOG.de.md](app/backend/CHANGELOG.de.md) |
| Roadmap data (What's new)              | [app/backend/ROADMAP.yaml](app/backend/ROADMAP.yaml)     |
| Feature ideas and roadmap (Nov 2026)   | [docs/ideas-roadmap-2026-11.md](docs/ideas-roadmap-2026-11.md) |
| Accessibility statement                | [docs/accessibility.md](docs/accessibility.md)           |

Proposals, kept for reference:
[docs/platform-split-frontends.md](docs/platform-split-frontends.md),
[docs/platform-split-club-isolation-twint.md](docs/platform-split-club-isolation-twint.md).

## Project structure

```
├── docker-compose.yml             # App stack (default, localhost)
├── docker-compose.traefik.yml     # Production routing behind Traefik (opt-in)
├── docker-compose.platform.yml    # Separate platform backend (opt-in)
├── settings.yaml                  # Deployment-time feature flags & limits
├── .env.example                   # Environment variable template
├── AGENTS.md                      # AI agent instructions
├── app/
│   ├── backend/                   # Flask + Celery
│   │   ├── hubra/                 # Application code (core/, api/)
│   │   ├── tests/                 # pytest (about 2500 tests)
│   │   ├── migrations/            # Alembic migrations (flask db migrate)
│   │   ├── API.md                 # Full API reference
│   │   ├── CHANGELOG.md           # Keep a Changelog (+ CHANGELOG.de.md)
│   │   ├── ROADMAP.yaml           # Planned items shown in What's new
│   │   └── wsgi.py                # Gunicorn entry point (ProxyFix)
│   ├── frontend/                  # Club app (React), e2e/ has the Playwright tests
│   ├── admin-frontend/            # Manage
│   ├── sso-frontend/              # Sign-in and account, also join.hubra.club
│   ├── support-frontend/          # support.hubra.club
│   ├── mcp/                       # Claude connector (MCP server)
│   └── deploy/
│       └── nginx/                 # Frontend start script (host names set at runtime)
├── packages/
│   ├── ui/                        # @hubra/ui, shared components and theme
│   └── api-client/                # @hubra/api-client
├── plugins/                       # Plugin docs and test helpers (plugins live in their own repos)
├── deploy/                        # Kubernetes: app/ base, clusters/contabo, vollbuild-ch, components/
├── modules/
│   └── mail/                      # Opt-in self-hosted mail stack, self-contained
│       ├── docker-compose.mail.yml  # Compose add-on (opt-in via -f)
│       ├── k8s/                   # Kubernetes manifests (opt-in)
│       ├── haraka/                # Inbound SMTP
│       ├── zonemta/               # Outbound SMTP
│       ├── certbot/               # TLS certificates
│       ├── cert-watcher/          # Hot-reload on renewal (Compose only)
│       └── scripts/               # validate-mail-config.py
├── brand/                         # Logo, icons, BIMI mark
├── tools/plugin_repo/             # Creates a new plugin repository from the template
├── docs/                          # All documentation
├── scripts/                       # init-env, smoke test, image reuse, sync
└── .github/                       # Workflows, rulesets, issue and PR templates
```

## Contributing

Bug reports, ideas and translation fixes are welcome; read
[CONTRIBUTING.md](CONTRIBUTING.md) before you write code. Code contributions
need the [contributor licence agreement](CLA.md). Everyone taking part follows
the [code of conduct](CODE_OF_CONDUCT.md). Report security problems as
described in [SECURITY.md](SECURITY.md), not in a public issue.

## License

Copyright (c) 2026 Mike Keller. All rights reserved.

The source is public so it can be read, but Hubra is not open source.
Running, self-hosting, modifying or redistributing it needs written
permission; see [LICENSE](LICENSE).
