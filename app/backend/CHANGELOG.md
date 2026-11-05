# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
The German version is CHANGELOG.de.md: add each entry there too, in the same
section and position, or the apps show that version in English.

## [Unreleased]

### Changed

- **Plugins stay in the club area**: a plugin's routes are served under `/api/v1/app/...` (old plugin paths like `/api/v1/bank` are rewritten, so plugin frontends and links keep working), and a plugin can no longer register routes in the platform or global areas, claim Hubra's tables or point at Hubra's own code. Plugins list the areas they extend under `uses:` in plugin.yaml, shown in the Plugin catalogue; a plugin touching an area it didn't list is refused. Event handlers of plugins run after the change is saved, in the worker, so a slow or failing plugin no longer holds up or rolls back saving an invoice or an event. Plugins can depend on other plugins with a version range (`depends:`); installing one installs what it needs first, and updates that would break a dependant are refused. See docs/plugins.md.
- **Background jobs fit their pod**: a Celery worker now starts two processes per CPU of its CPU limit (at least two) instead of one per CPU of the node. On a 6-CPU node a 1-CPU, 512 MiB worker used to start six processes, which do not fit in 512 MiB (they were killed for memory in a test) and took turns on one CPU. Set `CELERY_WORKER_CONCURRENCY` (or `--concurrency`) to choose another number. See docs/scaling.md.
- **Fewer database queries for platform settings**: the first platform setting read in a transaction loads them all in one query. A setting without a stored value used to cost a query on every read (`relay()` alone made six), and every secret setting also read its encryption key from the database.
- **Sign-ins no longer wait for the "new device" mail**: the mail is queued and sent by the worker.
- **The diagnostics health check answers within its time limit**: a check still running after one second is reported as a timeout. Before, the answer waited until every check ended, so an unreachable mail server held it for several seconds.
- **The API is split into three areas**: `/api/v1/platform` (manage, served by the platform backend), `/api/v1/app` (the club app) and `/api/v1/global` (sign-in, account, translations, version, public data, club directory and invites). The apps call the new paths. The old ones (`/api/v1/members`, `/api/v1/manager/...`, `/api/v1/system/...`) still work and are rewritten to the new ones, so open browser tabs, plugins and links in sent mail keep working. See docs/platform-backend.md.
- **Each API area has its own backend image** (`backend`, `global-backend`, `platform-backend`, one build under three names): on k3s, sign-in and account (`/api/v1/global`) run in their own `global-backend` Deployment, so the club app, sign-in and the platform can each be pinned, rolled and scaled on their own. See docs/platform-backend.md.

- **Separate platform backend** (k3s, optional on Compose): the platform API (`/api/v1/manager`, `/api/v1/admin`, `/api/v1/system`), the platform jobs (backups, checks, upgrades, plugins, alerts), migrations and the scheduler run in their own `platform-backend` and `platform-worker`, from the same build published as `ghcr.io/hubra-app/hubra/platform-backend`. A platform-only update no longer restarts the club backend. Keep the platform version the same as the club version or newer. See docs/platform-backend.md.
- **Manage navigation reorganised by task**: the sidebar has the sections Clubs, Operations, Services, Access & security and Hubra, and every page's tabs belong to one job. The catch-all Platform settings page is gone: each setting sits on the page it configures (mail relay and system sender under Mail, backup storage under Backups › Storage, Discord credentials and channels under Discord, plan limits under All clubs, alert delivery under Alerts › Rules, performance thresholds under Diagnostics › Performance). Club requests are a tab of All clubs, outbound mail and the mail server moved from Diagnostics to Mail, the Discord status to Discord, API permissions to Roles, performance from Alerts to Diagnostics, maintenance got its own page, and support access is a tab of the audit log. Old addresses redirect, so bookmarks and links in alert mails and Discord posts still open the right page.

- **No more "High API Error Rate" alert on every release**: the check counted 4xx and 5xx over the whole month, so the 401s from expired sign-ins after a restart set it off. It now counts server errors (5xx) in the last hour (every 10 minutes, at least 50 requests, threshold `API_ERROR_RATE_THRESHOLD`, 5 %), ignores errors in a backend's first two minutes, sends one alert per incident and a "back to normal" when it recovers.

- **System alerts go to the platform Discord log** instead of a webhook: `DISCORD_WEBHOOK_URL` is gone. Set the log channel in manage › Platform settings › Discord.

- **`FERNET_KEY` is required in production** (`.env` change): the backend no longer starts without it. Values stored before were encrypted with a key derived from `SECRET_KEY` and stay readable, so set a fresh key and run `flask crypto rotate`.

### Added

- **Support site at support.hubra.club**: one place for help, the roadmap, the system status and reports, in its own `support-frontend` image so it stays up while the rest of Hubra is upgraded. It has help articles with search, a set-up checklist for new clubs, the roadmap with voting (moved from sso.hubra.club/roadmap, which now forwards there, like /status), what's new, problem reports, ideas and a new contact form (cases of kind "question", their own tab in manage › Reports & ideas), "My reports" with the answers, a developer page (API tokens, the Claude connector, public data), a security page with security.txt, and "My data": download everything the account holds as JSON, and delete the account once it is in no club (it is anonymised and every sign-in ends). It signs in through SSO with the same account. Mails to reporters link there once the platform setting `support.url` is set (manage › Reports & ideas). The club app's account menu links it as "Help and support". See docs/support-site.md.

- **Modules in plans, and module prices per member or per licence**: in manage › All clubs › Plans & prices a plan lists the modules and plugins it includes, each either at no extra cost or with its own price in that plan. Every module price (in a plan, as an add-on list price, or on a club) is flat, per member (members that are not archived) or per licence. A club's billing counts the plan's modules and its add-ons with their quantities (licences are set per club), and an add-on on the club replaces the plan's price for that module. The public pricing API lists each plan's modules, the unit of each add-on price and which public plans include it (docs/public-api.md).

- **Clubs set up their own backup key**: Settings › Encryption in the club app walks club admins through it: what the key is for, generating an age key pair in the browser (the private key never reaches the server), storing it safely (download or copy, with tips) and proving it was stored by pasting or choosing the key file before the public key is saved. Afterwards the tab shows the key, when and by whom it was set, the last backup encrypted to it, a check for the stored key, replace and remove, and how to open a backup with `age`. Clubs that already have an age key can paste its public key. New API `GET/PUT/DELETE /api/v1/admin/backup-key` (club admins); a private key sent there is refused. A club can also choose **Only our key** (typed confirmation): new backups are then encrypted to the club key alone and Hubra can no longer restore them; manage › Encryption marks these clubs.

- **Platform admins in Discord** (needs Discord plugin 2.3.0): club requests in the platform log get Approve / Reject buttons (Reject asks for the reason), alerts get Acknowledge, Silence 1 h and Open in manage, and turn green when the problem is gone. On the platform server, `/plattform status|verein|backup` and `/wartung jetzt|planen|ende|abbrechen` (`planen` makes a planned window for every club). New platform log categories: daily digest at 08:00, release notes for each new version, and security pings (platform admins on a new device or without two-factor, many failed sign-ins from one address, encryption keys over a year old). Only linked platform admins with two-factor and the matching permission may use them. Clubs can opt in to release and maintenance notices on their server. Discord interactions now pass the maintenance gate. See docs/discord.md, "Platform admins in Discord".

- **Roles on the platform server** (manage › Platform settings › Discord, off by default): everyone who linked Discord gets Plattform-Admin (platform staff with two-factor), Vereinsinhaber, Vereinsadmin and Vereinsmitglied on the platform log's server, kept up to date every ten minutes and right after linking. The bot makes these roles itself without permissions and never touches others; turning it off deletes them. The bot needs Manage Roles there.

- **What's new and roadmap**: the club app's Neuigkeiten opens the newest release (first six changes, "show all" for the rest) with earlier versions folded below, five at a time, and a Roadmap tab; the menu marks Neuigkeiten with a dot until the newest notes are read. Manage has a page for both under Hubra › Neuigkeiten & Roadmap (the changelog left Diagnostics). The roadmap comes from `app/backend/ROADMAP.yaml` (now / next / later / done, German and English) via the public `GET /api/v1/version/roadmap`. The changelog is now in German too (`CHANGELOG.de.md`, `GET /api/v1/version/changelog?lang=de`).

- **Maintenance mode**: manage › Alerts › Overview or `flask maintenance on|off|status [--minutes N] [--message TEXT]`. The club apps show a maintenance page (club API answers 503 `MAINTENANCE`), manage, sign-in and account keep working, alerts pause, and it ends on its own at the set time. `GET /api/v1/maintenance` is public.
- **Alert rules** (manage › Alerts › Rules): master switch for all alert mails and Discord posts (`alerts.enabled`), and per alert type mail and Discord on or off (`alerts.mail_off`, `alerts.discord_off`). `GET/PUT /manager/platform/alerts/switches`, `GET/PUT /manager/platform/maintenance`.

- **Confirm platform actions with a passkey**: manage's "Passwort bestätigen" dialog (plugin installs, updates and sources, signing keys, backup restore/delete, key rotation, opening a club as a member) offers "Mit Passkey bestätigen" to accounts with a passkey. It opens SSO `/confirm` in a small window, since passkeys belong to the SSO address. New `GET /account/step-up`, `POST /account/step-up/passkey/options` and `POST /account/step-up/passkey`; the challenge is tied to the account and the sign-in and cannot be used to sign in. Same ten-minute window as the password, which stays as the fallback. Passkey-only accounts can still confirm with the password and a recovery code.
- **Discord bot status** (manage › Diagnostics › Discord): settings, the bot's sign-in (live, cached 5 minutes, "Check now"), servers it is on, the Interactions Endpoint URL against the expected one, the platform log channel with last post and failure, the plugin, linked accounts, every club server with its last error, and the redirect URIs and interactions URL to enter in the Developer Portal. A bad token, an unreachable log channel or failing log posts show on manage › Alerts. docs/discord.md has a step-by-step setup with permissions and redirects.

- **Members choose their notifications**: Konto › Mitgliedschaft › Benachrichtigungen lists the topics (new posts, events, polls; reminders; my sign-ups; votes in my polls; tasks for me) with bell, browser push and, for reminders, mail. Security notices always come. Migration `d6f2b8e4a1c7` adds `members.notify_prefs`; `GET/PUT /members/me/notifications`.
- **Alert settings**: manage › Platform settings › Alerts sets the alert mail cooldown (`alerts.cooldown_minutes`, 60), event log retention (`alerts.retention_days`, 30) and the manage address for the button in alert mails (`alerts.manage_url`, falls back to `MANAGE_BASE_URL`). Alert mails now go to platform admins only (superadmins and roles with `platform.settings`), not to Support.
- **Platform log on Discord**: the Hubra bot posts platform events (clubs, club requests, roles and impersonation, plugins, backups, platform settings, system alerts) to a channel on the platform's own Discord server. Platform settings `discord.log_channel_id` and `discord.log_events`, a test button and an invite link in manage › Platform settings › Discord. Club requests submitted, approved and rejected are now in the platform audit log. See docs/discord.md, "Platform log".

- **Platform alerts page** (manage › Platform › Alerts): open problems right now, latest alerts, 24 h counts per area, the event log (moved from Diagnostics) and each admin's alert mail choices. New alert sources: database/Redis/IMAP outages and recoveries (from the 20 s health check, after a minute down), failed scheduled backups, plugin updates (off by default). Alert mails use the Hubra mail layout (level badge, details box, time and instance, a button to the alerts page when `MANAGE_BASE_URL` is set) in the admin's language. Merge migration `a6e2c8f4b1d7` joins the two heads left by #97 and #98.
- **Outbound mail monitoring**: manage › Diagnostics has an Outbound mail tab (main and fallback relay checked every 5 minutes by logging in, "Check now", sent/fallback/failed counts for 24 hours, "Use the main relay again now") and an Event log tab (every mail sent or failed, relay outages, system alerts; 30 days). Platform staff get alert mails when a relay goes down or comes back, the fallback takes over, a mail cannot be delivered, or a system alert fires, and choose which ones they get. Migration `b5d9e3f7a1c6` adds `platform_events` and `users.platform_alerts`.
- **Key rotation for secrets at rest**: `FERNET_OLD_KEYS` keeps old keys readable, `flask crypto rotate` re-encrypts every stored secret in every club schema, `flask crypto check` confirms nothing is left on an old key. See docs/operator-guide.md, "Change the encryption key".
- **Public-key backups**: with `BACKUP_PUBLIC_KEY` (an age key from `flask backups keygen`) backups are encrypted so the server can write but not read them; restore and full verify ask for the private key, which is used once and never stored. A club can have its own key (`flask backups club-key`) and open its own backups. Verify without a key checks the file's checksum. `.dump.gpg` backups still open with `BACKUP_ENCRYPTION_KEY`. Migration `d1a7c3e9b5f2` adds `tenants.backup_public_key`; the backend image now ships `age`.
- **Per-club encryption keys**: every club (and the platform) has its own random data key (`data_keys`, migration `e3b9d5f1a7c4`), wrapped by `FERNET_KEY`. Values are AES-256-GCM and bound to their club and column, so a value never opens in another club. Changing the master key only rewraps one row per club. New club keys from manage › Platform settings › Encryption or `flask crypto rotate --new-keys [--club <slug>]`; deleting a club for good deletes its keys. **After upgrading, press Re-encrypt there (or run `flask crypto rotate`) once.**
- **Backup public key as a platform setting** (`backup.public_key`, default `BACKUP_PUBLIC_KEY`), and each club's backup key in the Encryption tab.
- **One public roadmap**: the planned items and the ideas from clubs are one list everywhere (Neuigkeiten › Roadmap, Feedback › Roadmap, sso /roadmap, manage and hubra.club/roadmap/), with a new "Ideas" column. People vote for planned items that are next or later, too, and staff can link an idea to a planned item (manage › Reports & ideas › idea › "Part of a planned item") so its votes count there. Settings › Modules has "Missing a module?", which opens the idea form with the new area "Module"; manage filters reports by area.
- **Performance › slow queries say when the pod was held back**: a slow query (and a slow request) is marked when its container used up its CPU limit or reached its memory limit while the request or task ran. A trivial statement that is slow with this mark waited for the CPU, not for the database.
- **Performance › requests without a route**: requests no API route matches (scanners, old links) are listed by path shape; ids and tokens are shown as `*`.

- **API tokens** (`Authorization: Bearer hbr_…`), backend only for now: personal tokens for one member in one club, club tokens made by club admins, and read-only platform tokens for platform admins. A token acts as its person, can only narrow their current rights to the scopes picked (read-only by default), is shown once and stored as a hash, expires after at most a year (platform tokens 30 days), and never opens account, sign-in, token, step-up or plugin routes. Making one needs two-factor sign-in and a fresh password confirmation. Members only get personal tokens when the club allows it. See docs/api-tokens.md.
- **Claude connector** (new image `mcp`, at mcp.hubra.club): an MCP server that lets Claude read Hubra with a person's own API token. It has no database access and no credentials of its own, so Claude sees only what the token may. Every tool only reads: platform diagnostics (health, alerts, route and query performance, errors, jobs, events, mail, Discord, maintenance) with a platform token, and members, events, attendance, groups, invoices, finances, polls, inventory and the audit log with a club token, plus `whoami` and a general read tool. Club data reaches it only when the club switches on "Allow AI assistants" (off by default). Claude Code connects with `claude mcp add --transport http hubra https://mcp.hubra.club/mcp --header "Authorization: Bearer hbr_…"`. On Compose it starts with `--profile mcp`. See docs/mcp.md.
- **Manage › Access & security › API tokens**: platform admins make, edit, replace and revoke their read-only platform tokens there (the secret is shown once, with the Claude Code command), and those with platform settings see and revoke every token of every club. The connector's address is the platform setting `mcp.url`.
- **Sign in to Hubra from other apps (OAuth)**: Claude (claude.ai and Claude Code) now connects to the Claude connector by signing in, without copying a token. On the sign-in page the person picks the club (or, for platform admins, the platform) and for how long (30 or 90 days, platform 7 or 30); the app then reads what that person may see and nothing more, through an access token that lasts an hour and renews itself. A token for the connector works only through the connector, and a club's data reaches it only while the club allows AI assistants. Everyone sees and ends their apps under SSO › My account › Apps; club admins see every token and app of their club under Settings › API & apps, where they also switch members' access and AI assistants on or off; platform admins register other apps (for the Hubra API, with or without a secret) under manage › Access & security › API tokens › Apps (OAuth), and choose whether apps such as Claude may register themselves (on by default, only with return addresses on claude.ai, claude.com or localhost). After the deploy: `flask db upgrade`. See docs/oauth.md.

### Fixed

- **Plugins with routes were refused after the OAuth change** ("route prefix overlaps / of core"): the blueprint for the OAuth `/.well-known` metadata has no prefix, so the plugin check saw core owning the whole site. A core blueprint on the site root is now treated like an area root and blocks no plugin.
- **Finance pages failed for clubs created before the recurring-transaction and invoice-period changes**: those two migrations changed only the template tables, so older clubs had no `transactions.recurring_id`, `invoices.period_start`/`period_end` or `recurring_transactions` table, and Transactions, Invoices and My invoices answered a server error. A migration adds what is missing, and every start now runs `flask sync-tenant-schemas`, which adds any table or column a club schema lacks (it never drops anything).
- **Diagnostics showed no running processes and a stale health cache after one slow Redis answer**: reading the build reports now waits up to a second and reports "unknown" instead of "not reporting", and a slow read no longer hides the health cache or lets the upgrade check decide from the worker's own build alone.
- **The Discord status read through an API token** (the Claude connector) gave the backend's in-cluster address as the expected interactions URL. Without `API_PUBLIC_URL` it is now unknown in that case.
- **Platform roles were empty**: manage › Rollen showed no platform roles and an empty permission list, so no permission could be given to a role. The platform permissions and default roles were only written by `flask seed-global-rbac`, which no deployment ran. `flask sync-permissions` (run on every start) now writes them too. Default roles: Platform admin, Manager, Support, the new Read-only, and Requester. A default role that already exists keeps the permissions it has; only Platform admin, whose permissions are locked, is completed on each start.
- **Discord security ping for platform admins on a new device** was never sent after an account sign-in (SSO, manage): it waited for a commit that came before it. It is now queued before that commit.

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
