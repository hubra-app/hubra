# Configuration

## Environment variables (`.env`)

See `.env.example` for the full list with descriptions.

Every mail Hubra sends (sign-in, invoices, notices) goes through an SMTP
relay at any provider: set `SMTP_*` here or later in manage › Mail. Club
mailboxes are the `mail` module, which needs the opt-in self-hosted mail stack
([modules/mail/README.md](../modules/mail/README.md)). Without mail, leave the
mail variables blank.

### Key groups

| Group       | Variables                                                                  | Required when                                            |
| ----------- | -------------------------------------------------------------------------- | -------------------------------------------------------- |
| Database    | `POSTGRES_*`, `DATABASE_URL`                                               | Always                                                   |
| Auth        | `SECRET_KEY`, `JWT_SECRET_KEY`                                             | Always                                                   |
| Encryption  | `FERNET_KEY`, `FERNET_OLD_KEYS` (old keys, still read during a rotation)   | Always in production, see [operator-guide.md](operator-guide.md#encryption-keys) |
| Redis       | `REDIS_URL`, `RATE_LIMIT_STORAGE`                                          | Always (Celery broker + rate limiting)                   |
| CORS        | `CORS_ORIGINS`                                                             | Always (comma-separated allowlist, no wildcards)         |
| JWT cookies | `JWT_COOKIE_DOMAIN`, `JWT_COOKIE_SAMESITE`, `JWT_COOKIE_SECURE`            | Production (cross-subdomain auth)                        |
| Frontend    | `FRONTEND_BASE_URL`                                                        | Production (email link generation — points at the SPA)   |
| API origin  | `API_PUBLIC_URL`                                                           | Production with outside services (callback URLs they call, e.g. `https://api.hubra.club`) |
| Manage      | `MANAGE_BASE_URL`                                                          | Optional fallback for the platform setting `alerts.manage_url` (the "Open alerts" button in alert mails) |
| Superadmins | `SUPERADMIN_EMAILS` (comma-separated; promoted on every start, never demoted) | Optional; or `flask make-admin --email <email>` |
| Domain      | `MAIL_HOST`, `MAIL_FROM`, `MAIL_DOMAIN`                                    | Always (mail vars only when mail enabled)                |
| Modules     | Per club in Settings › Modules, or `flask modules enable <code>` | Always                                                   |
| SMTP/IMAP   | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FALLBACK_*`, `IMAP_HOST`, `IMAP_PORT` | Sending mail (any SMTP relay); `IMAP_*` only for the IMAP health check |
| Backups     | `BACKUP_S3_*`, `BACKUP_PUBLIC_KEY` (`BACKUP_PRIVATE_KEY` optional, `BACKUP_ENCRYPTION_KEY` for older backups) | Backups enabled |
| Files       | `FILES_S3_*` (endpoint, bucket, region, access/secret key), `FILES_MAX_MB` (25), `FILES_DIR` (`/var/lib/hubra/files`, used without a bucket) | Clubs' files (e.g. the documents plugin); also in manage › Backups › Storage |
| Payments    | `STRIPE_SECRET_KEY` (live Connect platform key, `sk_live_…`) | Online invoice payments with the payments plugin (card, TWINT); better set in manage › Payments, with the sandbox key, the Stripe mode (sandbox or live) and the Hubra fee (docs/billing.md, "Sandbox and live") |
| Club domains | `CUSTOM_DOMAIN_TARGET` (host clubs CNAME to) | Serving club domains on Kubernetes with cert-manager; switch, issuer, ingress class and Service in manage › Club domains (docs/operator-guide.md#kubernetes) |
| Workers     | `CELERY_WORKER_CONCURRENCY`, `CELERY_TASK_SOFT_TIME_LIMIT` (900 s; hard limit one minute later), `CELERY_MAX_TASKS_PER_CHILD` (500), `CELERY_MAX_MEMORY_PER_CHILD` (250000 KiB), `HUBRA_PLATFORM_QUEUE`, `HUBRA_BULK_QUEUE` | Optional, see [scaling.md](scaling.md#job-defaults) |
| Database limits | `DB_STATEMENT_TIMEOUT_MS_API` (60000), `DB_IDLE_IN_TX_TIMEOUT_MS_API` (120000), `DB_STATEMENT_TIMEOUT_MS_WORKER` (300000), `DB_IDLE_IN_TX_TIMEOUT_MS_WORKER` (0 = off) | Optional, see [scaling.md](scaling.md#job-defaults) |
| Plugins     | `HUBRA_PLUGIN_DIR`, `HUBRA_PLUGINS_RELOAD_POLL`, `HUBRA_OFFICIAL_INDEX`, `HUBRA_PLUGINS_ALLOW_PRIVATE` (1 = allow a repository on a private address) | Optional, see [plugins/README.md](../plugins/README.md)  |

## Platform settings and club settings

Some settings belong to the whole platform, others to one club.

**Platform settings** live in the public `platform_settings` table and are
edited in manage under the page each setting belongs to (**Mail**, **Backups › Storage**, **Discord**, **All clubs › Plan limits**, …) (global permission
`platform.settings`, superadmins have it). Each one starts from its env
variable; a value saved there overrides env until you press "Reset to env".

| Setting                                   | Env default                                  |
| ----------------------------------------- | -------------------------------------------- |
| Mail relay host, port, user, password     | `SMTP_HOST` (else `ZONEMTA_SMTP_HOST`), `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` |
| Fallback relay host, port, user, password | `SMTP_FALLBACK_HOST` (empty = none), `SMTP_FALLBACK_PORT`, `SMTP_FALLBACK_USER`, `SMTP_FALLBACK_PASSWORD` |
| System sender address and name            | `MAIL_FROM`, "Hubra"                         |
| Backup storage (S3 endpoint, bucket, region, keys) | `BACKUP_S3_*`                        |

Every mail Hubra sends goes through the relay. Sign-in, SSO and account
mail always comes from the system sender. Club mail comes from the system
sender with the club's address as Reply-To, unless the club has its own
sender mailbox from the mail module; that mailbox logs in to the mail
module's server (`ZONEMTA_SMTP_HOST`), or to the relay without one.
The backup keys stay in env only.

**Fallback relay.** When a fallback host is set and the relay refuses a
mail (send quota reached, outage, bad login), the mail goes out again
through the fallback, from the same sender. After such a switch the relay
is skipped for 15 minutes (kept in Redis), so a quota does not cost a
failed attempt per mail. A refused recipient also tries the fallback but
does not start those 15 minutes, since one bad address says nothing about
the relay. Club mailboxes from the mail module never use the
fallback. For Brevo: host `smtp-relay.brevo.com`, port 587, your Brevo
SMTP login and SMTP key, and verify the sender domain in Brevo (SPF/DKIM),
or receivers will reject the mail.

**Monitoring the relays.** manage › Mail › Outbound
shows both relays: every 5 minutes Hubra connects and logs in to each
(EHLO, STARTTLS, AUTH) without sending anything, and "Check now" does the
same by hand. A relay counts as down after two failed checks in a row.

**Platform alerts.** manage › Alerts shows the open problems
(background jobs not running, the database, Redis or IMAP unreachable, a
relay down, mail going through the fallback, undelivered mail, a failed or
missing scheduled backup), the latest alerts and 24 hours of warnings and
errors per area. Its Event log tab lists every mail handed to a relay (sent,
sent through the fallback, or failed, with the relay and the error; never
the body), relay and service outages, failed scheduled backups, plugin
news, system alerts and the alerts themselves, for 30 days (table
`platform_events`). Platform staff (superadmins and anyone with
`platform.diagnostics`) get alert mails for: a relay down or back, the
fallback taking over, undelivered mail (a refused recipient address does
not count), a service down for a minute or back, a failed scheduled backup,
plugin news (off by default) and the system alerts (disk, failed tasks, API
error rate). Each type except outages, recoveries and plugin news goes out
at most once an hour; each admin turns types on or off on the My alerts
tab. Alerts go through the relays, so when both are down they only reach
the event log (and Discord). A database outage is mailed once it is over,
with how long it lasted. Stopped background jobs cannot report themselves:
watch the public `/health` endpoint from outside for that.

The **Rules** tab switches alerts for the whole platform: a master switch
(`alerts.enabled`; off sends nothing by mail or to Discord, the event log
and the overview keep everything) and, per type, mail and Discord
(`alerts.mail_off`, `alerts.discord_off`). The API error-rate alert counts
only server errors (5xx) in the last hour, needs at least 50 requests,
leaves out errors in the first two minutes after a backend starts and is
sent once per incident, with a "back to normal" when the rate drops. An
expired sign-in after a release (401) is not an error.

**Maintenance mode** (manage › Maintenance, or
`flask maintenance on --minutes 15 --message "…"` / `flask maintenance off`):
the club apps show a maintenance page and the club API answers 503;
manage, sign-in and account pages keep working. All alerts are paused and
requests are not counted for the error rate. It ends on its own at the set
time (`maintenance.enabled`, `maintenance.message`, `maintenance.until`).

**Backups** are platform-only too: manage › Backups (global
permission `backups.manage`; superadmins have it). There is no backup of the
whole database: the global backup holds the public schema (accounts, clubs,
platform settings), and each club has its own backups, so one club can be
restored on its own. Scheduled daily, weekly and monthly runs make one global
backup and one per club without anyone pressing a button. There is no club
Backups module any more. See [disaster-recovery.md](disaster-recovery.md).

**Club settings** (name, contact addresses, sender name, modules) are kept
per club and edited by the club's owners and admins (where each kind is
stored, and what every setting does: [settings/](settings/README.md)). They no longer
include an SMTP server or backup storage. If you had typed those into a
club's settings screen rather than env, enter them once under Platform
Settings: the migration that removed them doesn't carry them over.

**Who uses what:** platform staff (anyone with a global permission) and club
owners/admins sign in to manage. Everyone else uses the club app, and starts
or finds a club on the SSO site (`/start`, `/clubs`), which is also served as
`join.<domain>` (`HUBRA_JOIN_HOST`).

### Cross-origin auth variables

These are critical when the API and frontend are on different subdomains
(`api.hubra.club` vs `app.hubra.club`). See
[architecture.md](architecture.md#cross-origin-auth) for why.

```
CORS_ORIGINS=https://app.hubra.club,https://manage.hubra.club,https://sso.hubra.club,https://join.hubra.club,https://support.hubra.club
JWT_COOKIE_DOMAIN=.hubra.club
JWT_COOKIE_SAMESITE=Lax
JWT_COOKIE_SECURE=true
FRONTEND_BASE_URL=https://app.hubra.club
```

## Settings (database)

Club-specific settings stored in the database `settings` table, managed
through the Settings UI or `/api/v1/settings/` API.

### Examples

| Key                           | Description                                                     |
| ----------------------------- | --------------------------------------------------------------- |
| `club.name`                   | Club display name                                               |
| `club.email_schema`           | Email address schema (`firstname.lastname`, `f.lastname`, etc.) |
| `mail.retention_default_days` | Global default message retention period                         |

> `FRONTEND_BASE_URL` (env) replaces the old `club.domain`-based URL generation
> for email links. Password-reset and email-verification links now point at the
> frontend SPA, not the API host.

## Limits (`settings.yaml`)

Deployment-time settings at the project root. Override any value at runtime
via environment variables using double-underscore as a nested delimiter:
`LIMITS__MAX_MEMBERS=50`.

Which modules (events, finance, mail, ...) a club uses is not set here: club
admins switch them under Settings › Modules, and platform managers can block
a module per club. See `app/backend/hubra/modules/README.md`.

```yaml
limits:
  # 0 = unlimited
  max_members: 0
  max_events_per_month: 0
```
