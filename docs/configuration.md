# Configuration

## Environment variables (`.env`)

See `.env.example` for the full list with descriptions.

The mail stack is **opt-in**. Switch on the `mail` module (`flask modules enable mail`, or Settings › Modules & plugins)
and configure the Infomaniak IMAP/SMTP variables to enable mail. If you are
not using mail, leave the mail variables blank.

### Key groups

| Group       | Variables                                                                  | Required when                                            |
| ----------- | -------------------------------------------------------------------------- | -------------------------------------------------------- |
| Database    | `POSTGRES_*`, `DATABASE_URL`                                               | Always                                                   |
| Auth        | `SECRET_KEY`, `JWT_SECRET_KEY`                                             | Always                                                   |
| Redis       | `REDIS_URL`, `RATE_LIMIT_STORAGE`                                          | Always (Celery broker + rate limiting)                   |
| CORS        | `CORS_ORIGINS`                                                             | Always (comma-separated allowlist, no wildcards)         |
| JWT cookies | `JWT_COOKIE_DOMAIN`, `JWT_COOKIE_SAMESITE`, `JWT_COOKIE_SECURE`            | Production (cross-subdomain auth)                        |
| Frontend    | `FRONTEND_BASE_URL`                                                        | Production (email link generation — points at the SPA)   |
| API origin  | `API_PUBLIC_URL`                                                           | Production with outside services (callback URLs they call, e.g. `https://api.hubra.club`) |
| Discord     | `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`, `DISCORD_BOT_TOKEN`, `DISCORD_PUBLIC_KEY` | Optional: the Hubra Discord bot and linking Discord accounts (see `docs/discord.md`) |
| Superadmins | `SUPERADMIN_EMAILS` (comma-separated; promoted on every start, never demoted) | Optional; or `flask make-admin --email <email>` |
| Domain      | `MAIL_HOST`, `MAIL_FROM`, `MAIL_DOMAIN`                                    | Always (mail vars only when mail enabled)                |
| Modules     | Per club in Settings › Modules & plugins, or `flask modules enable <code>` | Always                                                   |
| SMTP/IMAP   | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `IMAP_HOST`, `IMAP_PORT` | Mail feature enabled (Infomaniak SMTP/IMAP)        |
| Backups     | `BACKUP_S3_*`, `BACKUP_ENCRYPTION_KEY`                                     | Backups enabled                                          |
| Plugins     | `HUBRA_PLUGIN_DIR`, `HUBRA_PLUGINS_RELOAD_POLL`, `HUBRA_OFFICIAL_INDEX`, `HUBRA_PLUGINS_ALLOW_PRIVATE` (1 = allow a repository on a private address) | Optional, see [plugins/README.md](../plugins/README.md)  |

## Platform settings and club settings

Some settings belong to the whole platform, others to one club.

**Platform settings** live in the public `platform_settings` table and are
edited in manage under **Platform › Platform Settings** (global permission
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
`BACKUP_ENCRYPTION_KEY` stays in env only.

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

**Backups** are platform-only too: manage › Platform › Backups (global
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
[SUBDOMAIN_MIGRATION.md](SUBDOMAIN_MIGRATION.md) for the full rationale.

```
CORS_ORIGINS=https://hubra.club,https://app.hubra.club,http://localhost:5173
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
admins switch them under Settings › Modules & plugins, and platform managers can block
a module per club. See `app/backend/hubra/modules/README.md`.

```yaml
limits:
  # 0 = unlimited
  max_members: 0
  max_events_per_month: 0
```
