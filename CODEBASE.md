# Club Management Suite — Codebase Reference

> Generated: 2026-07-09
> Source: [github.com/pixe-pine/club-management-suite](https://github.com/pixe-pine/club-management-suite)

---

## 1. Project Overview

**Club Management Suite** (codename _VollBuild_) is a self-hosted club management platform for makerspaces, associations, and similar member-based organisations. It provides member management, finance tracking, group communication, events, polls, an inventory system, and an integrated self-hosted mail stack (IMAP/SMTP).

The project is deployed via Docker Compose and uses a React SPA frontend with a Flask API backend. The optional mail stack adds WildDuck IMAP, Haraka inbound SMTP, and ZoneMTA outbound SMTP.

### Core domains

| Domain    | Description                                                                    |
| --------- | ------------------------------------------------------------------------------ |
| Members   | CRUD, archiving, email verification, password management, application workflow |
| Groups    | Organisational groups with membership management, group mail aliases           |
| Finance   | Transactions, invoices (Swiss QR-bill PDFs), budgeting, external parties       |
| Mail      | Mailbox/alias CRUD, member mail provisioning, WildDuck reconciliation          |
| Events    | Club events, workshops, attendance tracking                                    |
| Polls     | Member polling and voting                                                      |
| Posts     | Announcements and community posts with likes/comments                          |
| Inventory | Item tracking with categories and usage instructions                           |
| Settings  | Key-value configuration, feature flags, role-based permissions                 |
| Audit     | Immutable audit log of all administrative actions                              |
| Backups   | Encrypted S3-compatible backups (pg_dump + GPG)                                |

---

## 2. Architecture

### Request flow

```
                     ┌──────────────────────────┐
                     │  External Traefik         │ :443/:80
                     │  (TLS termination, ACME)  │
                     └──────┬───────────┬────────┘
                            │           │
               Host(cos.vollbuild.ch)  Host(api.vollbuild.ch)
                            │           │
                            ▼           ▼
                     ┌──────────────┐  ┌──────────────┐
                     │   Caddy 2    │  │   Backend    │
                     │  (frontend)  │  │  Flask API   │
                     │   :80        │  │  :5000       │
                     └──────┬───────┘  └──────┬───────┘
                            │                 │
                            ▼                 │
                     ┌──────────────┐         │
                     │   Frontend   │         │
                     │  React SPA   │         │
                     │  :80         │         │
                     └──────────────┘         │
                                              │
                              ┌───────────────┼──────────────┐
                              │               │               │
                              ▼               ▼               ▼
                      ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
                      │  PostgreSQL  │ │    Redis     │ │   MongoDB    │
                      │  (app data)  │ │ (queue+rate) │ │  (mail data) │
                      └──────────────┘ └──────────────┘ └──────┬───────┘
                                                               │
                      ┌───────────────────────────┼───────────────┐
                      │                           │               │
                      ▼                           ▼               ▼
              ┌──────────────┐            ┌──────────────┐ ┌──────────────┐
              │   Haraka     │◄─ port 25 ─│  WildDuck    │ │   ZoneMTA    │
              │ (inbound SMTP)│           │ (IMAP server) │ │(outbound SMTP)│
              └──────────────┘            └──────────────┘ └──────────────┘
```

1. **Browser → Traefik** — External Traefik terminates TLS and routes by Host header.
2. **Traefik → Caddy** (`cos.vollbuild.ch`) — Serves frontend HTML/JS with security headers and CSP.
3. **Traefik → Backend** (`api.vollbuild.ch`) — API requests go directly to Flask (no Caddy proxy).
4. **Flask ↔ PostgreSQL** — Member data, groups, finance, settings, audit log.
5. **Flask ↔ Redis** — Rate limiting storage, Celery broker.
6. **Celery tasks ↔ WildDuck API** — Async mailbox/alias provisioning, password sync, retention cleanup.

### Service topology

#### App stack (`docker-compose.yml`)

| Container       | Image                      | Role                                       |
| --------------- | -------------------------- | ------------------------------------------ |
| `caddy`         | `caddy:2.8-alpine`         | Frontend reverse proxy + security headers  |
| `frontend`      | Build from `app/frontend/` | React SPA served via nginx                 |
| `backend`       | Build from `app/backend/`  | Flask API (gunicorn, 2 workers, 4 threads) |
| `flask-init`    | Build from `app/backend/`  | One-shot migrations + seed                 |
| `celery-worker` | Build from `app/backend/`  | Async task worker                          |
| `celery-beat`   | Build from `app/backend/`  | Periodic task scheduler                    |
| `postgres`      | `postgres:16-alpine`       | Primary app database                       |
| `redis`         | `redis:7-alpine`           | Queue broker, rate-limit storage           |

#### Mail stack (`docker-compose.mail.yml` — opt-in)

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

### Network topology

- **edge** — Public-facing network (Caddy, Haraka inbound SMTP).
- **internal** — Private Docker network for inter-service communication.
- **cos_internal** — Production override network (Traefik integration).
- **frontend** — External Traefik network in production.

### Auth flow

Authentication uses JWT access tokens stored in **HttpOnly cookies** (not `localStorage`) with CSRF protection. Refresh tokens rotate access tokens. Key details:

- `JWT_TOKEN_LOCATION: ["cookies"]`
- `JWT_COOKIE_CSRF_PROTECT: True`
- `JWT_COOKIE_DOMAIN: .vollbuild.ch` (production)
- Access token TTL: 15 minutes (configurable)
- Refresh token TTL: 30 days

---

## 3. Directory Structure

```
club-management-suite/
├── AGENTS.md                    # AI agent configuration & development rules
├── CODEBASE.md                  # This file
├── README.md                    # Project overview & quick start
├── settings.yaml                # Deployment-time settings (feature flags, limits)
├── opencode.json                # OpenCode AI IDE configuration
├── skills-lock.json             # Locked agent skill versions
├── .pre-commit-config.yaml      # Pre-commit hooks (ruff, prettier, eslint, pytest)
├── .editorconfig                # Editor conventions
├── .gitignore                   # Git ignore rules
│
├── app/                         # Application source code
│   ├── backend/                 # Flask + Celery backend (Python)
│   │   ├── vollbuild/           # Application package (app factory, blueprints, models)
│   │   │   ├── api/             # Blueprint modules (32 domains)
│   │   │   │   ├── auth/        # Authentication & account management
│   │   │   │   ├── members/     # Member CRUD, archive, provisioning
│   │   │   │   ├── groups/      # Group management
│   │   │   │   ├── finance/     # Invoices, transactions, QR-bills
│   │   │   │   ├── mail/        # Mailboxes, aliases, provisioning
│   │   │   │   ├── events/      # Events & attendance
│   │   │   │   ├── polls/       # Polls & voting
│   │   │   │   ├── posts/       # Announcements & comments
│   │   │   │   ├── inventory/   # Item tracking
│   │   │   │   ├── settings/    # Key-value settings
│   │   │   │   ├── audit/       # Audit log
│   │   │   │   ├── backups/     # S3 backup management
│   │   │   │   ├── applications/# Membership applications
│   │   │   │   ├── dashboard/   # Aggregated dashboard data
│   │   │   │   ├── bindings/    # Discord/SSO bindings
│   │   │   │   ├── codes/       # Access codes
│   │   │   │   ├── functions/   # Club function roles (Kassier, Präsidium, etc.)
│   │   │   │   ├── i18n/        # Internationalisation
│   │   │   │   ├── notifications/ # Member notifications
│   │   │   │   ├── roles/       # Role-based permissions
│   │   │   │   ├── tiers/       # Membership tiers
│   │   │   │   ├── setup/       # Initial setup wizard
│   │   │   │   ├── health/      # Health check endpoint
│   │   │   │   ├── system/      # System info & version
│   │   │   │   ├── stream/      # Server-sent events
│   │   │   │   ├── version/     # Version endpoint
│   │   │   │   ├── features/    # Feature flag overrides
│   │   │   │   ├── fields.py    # Field-level permission definitions
│   │   │   │   ├── permissions.py # Permission decorators
│   │   │   │   └── utils.py     # API utilities
│   │   │   ├── models/          # SQLAlchemy models (28 files)
│   │   │   │   ├── member.py    # Member model
│   │   │   │   ├── group.py     # Group model
│   │   │   │   ├── finance.py   # TransactionCategory, Transaction, Invoice
│   │   │   │   ├── event.py     # Event model
│   │   │   │   ├── poll.py      # Poll/Vote models
│   │   │   │   ├── post.py      # Post/Comment/Like models
│   │   │   │   ├── mail.py      # MailLog
│   │   │   │   ├── managed_mail.py # ManagedMailAddress
│   │   │   │   ├── role.py      # Role, Permission, RolePermission
│   │   │   │   ├── inventory.py # InventoryItem, Category
│   │   │   │   ├── setting.py   # Setting (key-value)
│   │   │   │   ├── audit.py     # AuditLog
│   │   │   │   ├── application.py # MemberApplication
│   │   │   │   ├── notification.py # Notification
│   │   │   │   ├── translation.py # Translation
│   │   │   │   ├── backup.py    # Backup record
│   │   │   │   └── ...          # (28 files total)
│   │   │   ├── schemas/         # Marshmallow serialisation schemas (19 files)
│   │   │   ├── services/        # Business logic services
│   │   │   │   ├── wildduck.py  # WildDuck API client
│   │   │   │   ├── mail_provisioning.py # Mailbox provisioning logic
│   │   │   │   ├── managed_mail.py # Managed mail address service
│   │   │   │   ├── backup.py    # Backup orchestration
│   │   │   │   ├── binding_engine.py / binding_registry.py # SSO bindings
│   │   │   │   ├── email.py     # Transactional email (Brevo/SMTP)
│   │   │   │   ├── qr_bill.py / qr_reference.py # Swiss QR-bill PDF
│   │   │   │   └── key_service.py # Key rotation
│   │   │   ├── tasks/           # Celery tasks
│   │   │   │   ├── wildduck.py  # Mail provisioning tasks
│   │   │   │   ├── mail_sync.py # IMAP mailbox sync
│   │   │   │   ├── mail_tasks.py # Periodic tasks (retention, reconciliation)
│   │   │   │   ├── email_tasks.py # Async email sending
│   │   │   │   ├── finance_tasks.py # Invoice reminders
│   │   │   │   ├── backup_tasks.py # S3 backup tasks
│   │   │   │   ├── health_tasks.py # Health check tasks
│   │   │   │   ├── i18n_tasks.py # Translation cache refresh
│   │   │   │   ├── session_tasks.py # Last-seen updates
│   │   │   │   └── smoke.py     # Celery smoke test
│   │   │   ├── seeds/           # Seed data (settings, translations)
│   │   │   ├── templates/       # Jinja2 email templates
│   │   │   ├── seeds.py         # Main seed runner
│   │   │   ├── config.py        # Configuration classes (dev/prod/test)
│   │   │   ├── extensions.py    # Flask extension singletons
│   │   │   ├── errors.py        # Error handlers
│   │   │   ├── settings_loader.py # pydantic-settings loader
│   │   │   ├── logging_config.py # Structured JSON logging
│   │   │   ├── validators.py    # Custom validators
│   │   │   └── crypto.py        # Encryption utilities
│   │   ├── tests/               # Backend test suite
│   │   │   ├── conftest.py      # Fixtures
│   │   │   └── ...              # Tests per domain (28 test modules)
│   │   ├── migrations/          # Alembic/Flask-Migrate migrations
│   │   ├── Dockerfile           # Backend Docker image
│   │   ├── pyproject.toml       # Project metadata, mypy/pytest config
│   │   ├── requirements.txt     # Production dependencies
│   │   ├── requirements-dev.txt # Development dependencies
│   │   ├── wsgi.py              # WSGI entry point (gunicorn)
│   │   ├── API.md               # Full API reference (732 lines)
│   │   ├── BUILD.md             # Build instructions
│   │   └── CHANGELOG.md         # Release changelog
│   │
│   ├── frontend/                # React SPA (TypeScript)
│   │   ├── src/
│   │   │   ├── api/             # API client modules (25 files)
│   │   │   │   ├── client.ts    # Base fetch wrapper (JWT auth, CSRF, auto-refresh)
│   │   │   │   ├── auth.ts      # Auth endpoints
│   │   │   │   ├── members.ts   # Member endpoints
│   │   │   │   ├── groups.ts    # Group endpoints
│   │   │   │   ├── finance.ts   # Finance endpoints
│   │   │   │   ├── mail.ts      # Mail endpoints
│   │   │   │   └── ...          # Per-domain API modules
│   │   │   ├── components/      # Shared UI components
│   │   │   │   ├── Shell/       # App shell (sidebar, header, content)
│   │   │   │   ├── ui.tsx       # Common UI primitives (Toasts, etc.)
│   │   │   │   ├── MemberEditModal.tsx
│   │   │   │   ├── RichTextEditor.tsx
│   │   │   │   ├── MarkdownRenderer.tsx
│   │   │   │   ├── LanguageSwitcher.tsx
│   │   │   │   ├── ErrorBoundary.tsx
│   │   │   │   └── SetupWizardModal.tsx
│   │   │   ├── screens/         # Route-level page components
│   │   │   │   ├── public/      # Login, Apply, ForgotPassword, ResetPassword,
│   │   │   │   │                # VerifyEmail, Bootstrap, NotFound
│   │   │   │   └── private/     # Dashboard, Members, Finances, Mail, Operations,
│   │   │   │                    # Settings, System, AccessDenied
│   │   │   ├── context/         # React context providers
│   │   │   ├── theme/           # Mantine theme (colors, component overrides)
│   │   │   ├── locales/         # i18next translations (en, de-CH)
│   │   │   ├── types/           # TypeScript interfaces
│   │   │   ├── assets/          # Static assets
│   │   │   ├── App.tsx          # Root component with routing
│   │   │   ├── main.tsx         # Entry point (Mantine, React Query, Router)
│   │   │   ├── index.css        # Global styles
│   │   │   ├── constants.ts     # Shared constants
│   │   │   └── format.ts        # Formatting utilities
│   │   ├── e2e/                 # Playwright E2E tests
│   │   ├── public/              # Public static files
│   │   ├── Dockerfile           # Multi-stage Docker build
│   │   ├── nginx.conf           # Production nginx config
│   │   ├── vite.config.ts       # Vite configuration
│   │   ├── playwright.config.ts # Playwright config
│   │   ├── tsconfig.json        # TypeScript configuration
│   │   ├── eslint.config.js     # ESLint flat config
│   │   ├── postcss.config.js    # PostCSS + Mantine preset
│   │   └── package.json         # Dependencies & scripts
│   │
│   └── deploy/                  # Deployment config
│       └── Caddyfile            # Caddy reverse proxy config
│
├── docs/                        # Documentation
│   ├── architecture.md          # System architecture & request flow
│   ├── api-overview.md          # API endpoints & permissions
│   ├── frontend.md              # Frontend stack & structure
│   ├── mail-stack.md            # Mail stack architecture & tasks
│   ├── configuration.md         # Environment & settings
│   ├── project-management.md    # Milestones & project management
│   ├── disaster-recovery.md     # Backup & restore procedures
│   ├── frontend_issues.md       # Known frontend issues
│   └── SUBDOMAIN_MIGRATION.md   # Subdomain migration notes
│
├── mail/                        # Mail stack build contexts
│   ├── haraka/                  # Inbound SMTP (custom config)
│   ├── zonemta/                 # Outbound SMTP (custom config)
│   ├── certbot/                 # TLS certificate automation
│   └── cert-watcher/            # Hot-reload on cert renewal
│
├── scripts/                     # Utility scripts
│   ├── sync.py                  # Development sync utility
│   └── validate-mail-config.py  # Mail configuration validator
│
├── graphify-out/                # Knowledge graph (AST-based)
├── .agents/                     # Agent skills (AI coding tools)
├── .claude/                     # Claude-specific config & skills
├── .opencode/                   # OpenCode AI plugins
├── .vscode/                     # VS Code workspace settings
├── .venv/                       # Python virtual environment
└── .gsd/                        # GSD project management state
```

---

## 4. Key Technologies

### Frontend

| Technology     | Version  | Purpose                                                     |
| -------------- | -------- | ----------------------------------------------------------- |
| React          | ^19.2.6  | UI framework (hooks, functional components)                 |
| TypeScript     | ~6.0.2   | Type safety (strict mode)                                   |
| Vite           | ^8.0.12  | Dev server & build tool                                     |
| Tailwind CSS   | ^3       | Utility-first CSS                                           |
| Mantine        | ^7.17.8  | UI component library (core/hooks/form/notifications/tiptap) |
| React Router   | ^7.17.0  | Client-side routing                                         |
| TanStack Query | ^5.101.2 | Server state management                                     |
| i18next        | ^26.3.4  | Internationalisation (en, de-CH)                            |
| TipTap         | ^2.11.7  | Rich text editor (markdown export)                          |
| Tabler Icons   | ^3.44.0  | Icon library                                                |
| Zod            | ^4.4.3   | Schema validation (form resolver)                           |
| Playwright     | ^1.61.0  | E2E browser tests                                           |
| ESLint         | ^10.3.0  | Linting (flat config)                                       |
| PostCSS        | ^8.5.16  | CSS processing (Mantine preset)                             |

### Backend

| Technology              | Version/Constraint | Purpose                                    |
| ----------------------- | ------------------ | ------------------------------------------ |
| Python                  | 3.13 (runtime)     | Application language                       |
| Flask                   | ≥3.0               | Web framework (app factory pattern)        |
| Flask-SQLAlchemy        | ≥3.0               | ORM                                        |
| Flask-Migrate           | ≥4.0               | Alembic migrations (auto-generated)        |
| Flask-JWT-Extended      | ≥4.6               | JWT auth (HttpOnly cookies, CSRF tokens)   |
| Flask-Marshmallow       | ≥1.0               | Serialisation / schema validation          |
| Flask-CORS              | ≥4.0               | Cross-Origin Resource Sharing              |
| Flask-Limiter           | ≥3.5               | Rate limiting (Redis-backed)               |
| Marshmallow-SQLAlchemy  | ≥1.0               | Auto-schemas from models                   |
| Gunicorn                | ≥21.0              | Production WSGI server                     |
| Celery                  | ≥5.3               | Async task queue (Redis broker)            |
| psycopg2-binary         | ≥2.9               | PostgreSQL driver                          |
| Redis                   | ≥5.0               | Redis client                               |
| argon2-cffi             | ≥23.0              | Argon2id password hashing                  |
| zxcvbn                  | ≥4.4               | Password strength estimation               |
| python-json-logger      | ≥2.0               | Structured JSON log output                 |
| pydantic-settings[yaml] | ≥2.2               | Settings loader (settings.yaml + env vars) |
| weasyprint              | ≥62.0              | PDF generation (invoices, QR-bills)        |
| qrbill                  | ≥1.2               | Swiss QR-bill PDF generation               |
| brevo-python            | ≥3.0               | Transactional email (Brevo/SendinBlue)     |
| boto3                   | ≥1.34              | S3-compatible backup storage (Contabo)     |
| cryptography            | ≥41.0              | Symmetric encryption (codes at rest)       |
| nh3                     | ≥0.2               | SVG sanitisation                           |

### Data stores

| Technology | Version   | Purpose                                |
| ---------- | --------- | -------------------------------------- |
| PostgreSQL | 16-alpine | Primary app database (all domain data) |
| Redis      | 7-alpine  | Celery broker, rate-limit storage      |
| MongoDB    | 7         | Mail data (WildDuck — mail stack only) |

### Infrastructure

| Technology     | Version       | Role                                      |
| -------------- | ------------- | ----------------------------------------- |
| Docker Compose | V2            | Container orchestration                   |
| Caddy          | 2.8-alpine    | Frontend reverse proxy (security headers) |
| nginx          | alpine        | Frontend SPA static serving (production)  |
| Traefik        | (external)    | TLS termination, ACME, routing            |
| WildDuck       | latest (GHCR) | IMAP mail server                          |
| Haraka         | (custom)      | Inbound SMTP (SRS rewriting)              |
| ZoneMTA        | (custom)      | Outbound SMTP (DKIM-ready)                |

### Pre-commit hooks

| Hook                    | Purpose                                   |
| ----------------------- | ----------------------------------------- |
| ruff                    | Python linting + auto-fix                 |
| ruff-format             | Python formatting                         |
| prettier                | Frontend JS/TS/CSS/JSON/YAML formatting   |
| conventional-pre-commit | Enforces Conventional Commits in messages |
| frontend-lint           | Runs `npm run lint` on frontend changes   |
| frontend-build          | Runs `tsc -b && vite build` on changes    |
| backend-mypy            | Type checking (non-blocking)              |
| backend-pytest          | Runs backend tests (pre-push stage)       |

---

## 5. Development Workflow

### Prerequisites

- Docker & Docker Compose V2
- Node.js 22+ (for local frontend dev)
- Python 3.13+ (for local backend dev)

### Clone & configure

```bash
git clone <repo-url>
cd club-management-suite
cp .env.example .env         # Edit secrets
```

### Run with Docker (full stack)

```bash
# Start app stack (frontend + backend + databases + queue)
docker compose up -d

# Start app + mail stack (adds WildDuck, Haraka, ZoneMTA)
docker compose -f docker-compose.yml -f docker-compose.mail.yml up -d

# Rebuild after code changes
docker compose up -d --build frontend
docker compose up -d --build backend

# View logs
docker compose logs -f backend
```

### Run locally for development

#### Frontend

```bash
cd app/frontend
npm install
npm run dev          # Dev server at :5173 with HMR
npm run build        # Production build (tsc + vite)
npm run lint         # ESLint
npm run test:e2e     # Playwright E2E tests
```

Environment: `VITE_API_BASE=http://localhost:5000/api` (set in `app/frontend/.env`) directs API calls to the local Flask backend. The Vite dev server proxies `/api/*` when `VITE_API_BASE` is relative.

#### Backend

```bash
cd app/backend
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Set DATABASE_URL for PostgreSQL, or use default SQLite
export DATABASE_URL=sqlite:///dev.db
export FLASK_ENV=development

flask db upgrade       # Run migrations
flask seed             # Seed data
flask run              # Dev server at :5000
```

### Database migrations

```bash
# Always generate via Flask-Migrate, never hand-write
flask db migrate -m "Description of change"
flask db upgrade
```

Without a working PostgreSQL instance, spin up Docker (`docker compose up -d postgres`) or use SQLite temporarily. The config automatically strips PostgreSQL-specific pool options when the URI points to SQLite.

### Seeding

```bash
flask seed                          # Migrate + seed
flask seed --skip-migrate           # Seed only (when already migrated)
flask seed --drop                   # Drop all tables, migrate, seed
```

The seed command populates: settings key-value pairs, feature flags, roles & permissions, transaction categories, the Vorstand group, club functions (Kassier, Präsidium, Aktuar), managed mail addresses, and translations (en-GB, de-CH).

**Known issue:** ORM inserts via `db.session.commit()` inside the seed script may not persist to PostgreSQL from certain session contexts. The workaround is to use raw SQL (`engine.execute(...)`) if the ORM path fails.

### Testing

#### Backend

```bash
cd app/backend

# Run all tests (requires Redis for test_s11_backend_gaps.py)
python -m pytest tests/

# Run without the Redis-dependent test
python -m pytest tests/ --ignore=tests/test_s11_backend_gaps.py
```

312 tests pass when excluding `test_s11_backend_gaps.py`. Tests use SQLite in-memory database, in-memory rate limiting, and eager Celery tasks (no Redis needed for most tests).

#### Frontend

```bash
cd app/frontend
npm run build && npm run lint   # Build + lint check
npm run test:e2e                # Playwright E2E tests
```

### Pre-commit verification gate

Before every commit:

1. **Frontend modified** (`app/frontend/`): `cd app/frontend && npm run build && npm run lint`
2. **Backend modified** (`app/backend/`): `cd app/backend && python -m pytest tests/ --ignore=tests/test_s11_backend_gaps.py`

Both must pass before committing. This is also enforced by pre-commit hooks (`frontend-lint`, `frontend-build`, `backend-pytest`).

### Code quality tools

```bash
# Python: ruff (lint + format)
cd app/backend && ruff check . && ruff format .

# TypeScript: ESLint + TypeScript
cd app/frontend && npm run lint && npx tsc --noEmit
```

### Git workflow

- **Branch naming:** `type/scope-description` (e.g. `feat/member-export`, `fix/login-redirect`)
- **Commit format:** [Conventional Commits](https://www.conventionalcommits.org/) — `type(scope): description`
  - Enforced by `conventional-pre-commit` hook and `pre-commit-config.yaml`
- **Worktree isolation:** All implementation work must happen in an isolated git worktree (see `AGENTS.md` for the workflow)

### Environment configuration

| Variable             | Purpose                           | Required   |
| -------------------- | --------------------------------- | ---------- |
| `DATABASE_URL`       | PostgreSQL connection string      | Yes (prod) |
| `SECRET_KEY`         | Flask secret key                  | Yes (prod) |
| `JWT_SECRET_KEY`     | JWT signing key                   | Yes (prod) |
| `CORS_ORIGINS`       | Allowed CORS origins              | Dev        |
| `REDIS_URL`          | Redis connection                  | Opt        |
| `WILDDUCK_API_TOKEN` | WildDuck API access token         | Mail       |
| `BREVO_API_KEY`      | Brevo transactional email API key | Opt        |
| `BACKUP_S3_*`        | S3 backup credentials + GPG key   | Opt        |

Configuration classes (`DevelopmentConfig`, `ProductionConfig`, `TestingConfig`) in `vollbuild/config.py` inherit from `BaseConfig`. Environment variables take precedence over defaults. Production requires explicit validation via `ProductionConfig.validate()`.

### Feature flags

Controlled via `settings.yaml` at deploy time:

```yaml
features:
  polls: true
  events: true
  finance: true
  mail: true # Requires mail stack (WildDuck, Haraka, ZoneMTA)
```

Overridable at runtime via environment variables: `FEATURES__MAIL=false`.

### Deployment

Production deployment uses Docker Compose with an external Traefik reverse proxy for TLS termination:

```bash
# Production start
docker compose -f docker-compose.yml -f docker-compose.override.yaml up -d

# With mail stack
docker compose -f docker-compose.yml -f docker-compose.override.yaml \
               -f docker-compose.mail.yml up -d
```

The `docker-compose.override.yaml` adds Traefik labels (`cos.vollbuild.ch` / `api.vollbuild.ch`), sets `JWT_COOKIE_DOMAIN=.vollbuild.ch`, mounts live code volumes, and switches `VITE_API_BASE` to the production API URL. This file is **not** committed broadly — it lives in `.gitignore` and is maintained per-deployment.
