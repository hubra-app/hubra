# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed

- **`FERNET_KEY` is required in production** (`.env` change): the backend no longer starts without it. Values stored before were encrypted with a key derived from `SECRET_KEY` and stay readable, so set a fresh key and run `flask crypto rotate`.

### Added

- **Key rotation for secrets at rest**: `FERNET_OLD_KEYS` keeps old keys readable, `flask crypto rotate` re-encrypts every stored secret in every club schema, `flask crypto check` confirms nothing is left on an old key. See docs/operator-guide.md, "Change the encryption key".

## [0.6.0] - 2026-07-13

### Added

- **API call counting middleware**: Per-tenant Redis counters (`api:calls:{tenant_id}:{YYYY-MM}`) track monthly API usage with a 45-day TTL. OPTIONS/HEAD and health endpoints are excluded.
- **API error rate tracking**: Global Redis counters (`api:errors:count`, `api:errors:total`) for monitoring error rates across all requests.
- **Storage metrics collection**: Aggregates PostgreSQL schema size and WildDuck mail quota for per-tenant storage usage reporting.
- **Discord webhook alerting**: `send_alert()`, `alert_error()`, `alert_warning()`, `alert_resolved()` utilities using `urllib.request` (no new dependencies). Configurable via `DISCORD_WEBHOOK_URL`.
- **Celery task failure alerting**: `@task_failure` signal handler sends Discord alerts with 1-hour cooldown per task.
- **API error rate Celery task**: `check_api_error_rate_task` runs hourly, alerts when error rate exceeds configurable threshold.
- **Infrastructure health checks**: `check_disk_space()`, `check_redis_health()`, `check_postgres_health()` with Discord alerting and resolved notifications. Runs hourly via Celery beat.
- **Tenant usage stats now live**: `get_usage_stats()` returns real API call counts and storage bytes instead of hardcoded zeros.

### Changed

- Beat schedule updated: added `infra-checks-hourly` (minute 30) and `api-error-rate-hourly` (minute 15).
- `tasks/__init__.py` now includes `monitoring` and `infra_checks` task modules.

## [0.5.0] - 2026-07-12

### Changed

- **Roles/permissions are now per-tenant**: Moved `roles`, `permissions`, and `role_permissions` from global-only (public schema) into `TABLES_TO_CLONE` so each tenant gets its own role definitions and permission assignments. `_seed_tenant()` now creates the full role set (Admin, Manager, Members, Finances, Inventory, Member) with the correct permission matrix for each new tenant.

### Removed

- **Dead SystemUser model**: Deleted `vollbuild/models/system_user.py` and its `system_users` table — superseded by the `User` model.
- **Public schema role seeding**: Removed role/permission seeding from `flask seed` (public schema). Roles are now created per-tenant during provisioning only.

### Fixed

- **Missing model exports**: Added `EventRegistration`, `GroupMembership`, and `member_roles` to `models/__init__.py`.

## [0.4.2] - 2026-07-12

### Fixed

- **Tenant schema creation**: Fixed 5 plural/singular mismatches in `TABLES_TO_CLONE` (`settings`→`setting`, `feature_flags`→`feature_flag`, `translations`→`translation`, `backup_records`→`backup_record`, `invoice_reminder_histories`→`invoice_reminder_history`). These caused `create_tenant_schema()` to fail with `UndefinedTable`, rolling back the Tenant record and preventing tenant provisioning. Added regression test validating `TABLES_TO_CLONE` against the SQLAlchemy model registry.

## [0.4.1] - 2026-07-10

### Fixed

- **Polls UI**: Replaced small `<Button>` icon buttons with `<ActionIcon>` for remind/edit/delete actions. Added per-poll loading state tracking so loading spinners only appear on the specific poll being acted on, not all polls simultaneously.
- **Health check**: Removed WildDuck API, ZoneMTA SMTP, and Haraka SMTP health checks — all removed from the stack. Renamed `check_smtp_submission` → `check_smtp` (tests Infomaniak SMTP via `SMTP_HOST`/`SMTP_PORT`). Updated `check_imap` to test Infomaniak IMAP. Updated frontend service labels, `docs/configuration.md`, and `.env.example` to remove all WildDuck/ZoneMTA/Haraka references.
- **Frontend tab titles**: Added global `PageHead` to OperationsTabScreen, FinanceTabScreen, MembersTabScreen. Removed redundant `PageHead` from 20 tab content components — title context is already given by the tab group. Moved action buttons to lightweight action bars. Removed eyebrow props from Settings, System, Dashboard, Mail PageHeads.
- **401 redirect guard**: Added `_authFailed` flag to `apiFetch` so `onAuthFailure` is only called once per auth failure cycle. After triggering the redirect, returns a pending promise that never resolves — prevents error notifications from flashing before the SSO redirect completes.

## [0.4.0] - 2026-07-09

### Fixed

- **Type safety (mypy)**: Resolved all 192 mypy errors across 23 backend files. Added `[tool.mypy]` config with overrides for Flask-SQLAlchemy extensions (`db.Model`, `ma.Schema`). Fixed arg-type, union-attr, assignment, return-value, attr-defined, operator, and call-overload errors in auth, finance, health, i18n, mail, members, settings, setup, system, tiers, pricing, backup, mail_i18n, managed_mail, mail_provisioning, qr_bill, and task modules.
- **Frontend build (CI)**: Removed dead `useEffect` block in `PostDetailScreen` that called undefined state setters (`setPost`, `setComments`, `setLoading`), fixing TS2552 errors that blocked CI pre-commit pipelines.

### Changed

- **CI pre-commit job**: Added `npm ci` for frontend dependencies so `frontend-build` hook can run in CI pipeline.

## [0.3.0] - 2026-07-09

### Fixed

- **Financial precision**: Removed `float()` wrapper on `Invoice.amount` — Decimal values are now stored directly to the `Numeric(12,2)` column, preventing binary floating-point rounding errors in batch invoice generation.
- **Token leakage**: Password reset and email verification tokens moved from URL query parameters (`?token=`) to URL fragments (`#token=`), preventing leakage via browser history, server access logs, and Referer headers. Backend and frontend updated.
- **Log leakage (PII)**: Removed email addresses from `Member.__repr__` and `Application.__repr__` — GDPR-sensitive PII no longer written to application logs.
- **Log leakage (secrets)**: `Setting.__repr__` now masks values when `sensitive=True` — API keys, SMTP passwords, and banking credentials are no longer dumped to logs.
- **Stale test**: `test_double_vote_conflict` renamed to `test_vote_change_allowed` — `PollService.vote` intentionally allows vote-changing on open polls; test now asserts correct 200 response and vote movement.

### Added

- **Dedicated Fernet key**: New `FERNET_KEY` environment variable for encryption at rest. Falls back to `SECRET_KEY` derivation (legacy) when unset. Documented in `.env.example` with generation instructions.

### Changed

- **PostgreSQL port exposure**: Removed `5432:5432` port mapping from `docker-compose.yml` — database is now only accessible via the internal Docker network.
- **ZoneMTA supply chain**: Pinned `zone-mta-template` git clone to `v1.11.2` with `--depth 1` for reproducible, supply-chain-safe builds.
- **cryptography dependency**: Raised minimum to `>=42.0.4` (CVE-2023-50782 mitigation).
- **HSTS preload**: Added `preload` flag to `Strict-Transport-Security` header.
- **Trivy CI scan**: Raised severity gate from `CRITICAL` to `CRITICAL,HIGH`.
- **Trivy CI install**: Pinned to `v0.58.0` release tarball instead of curl-pipe-sh from `main` branch.
- **i18n upload limit**: Added 2 MiB size cap on translation file imports to prevent memory exhaustion.

## [0.2.0] - 2026-07-02

### Added

- Full Backend Password Reset Flow (via email) — Users can now reset their password if they forget it. This includes email verification and secure token handling.
- Two-Factor Authentication (2FA) Support — Users can enable 2FA for added security. This includes setup via authenticator apps and backup codes.
- Enhanced Logging and Monitoring — Integrated structured logging and monitoring for better observability of the application.

### Removed

- Weak password support — The system now enforces stronger password policies, removing support for weak passwords.

## [0.1.0] - 2026-07-02

### Added

- Initial versioned release baseline.
