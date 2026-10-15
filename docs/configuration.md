# Configuration

## Environment variables (`.env`)

See `.env.example` for the full list with descriptions.

The mail stack is **opt-in**. Set `features.mail: true` in `settings.yaml`
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
| Domain      | `MAIL_HOST`, `MAIL_FROM`, `MAIL_DOMAIN`                                    | Always (mail vars only when mail enabled)                |
| Features    | Toggled in `settings.yaml` (`features.mail`, `features.polls`, etc.)       | Always                                                   |
| SMTP/IMAP   | `SMTP_HOST`, `SMTP_PORT`, `IMAP_HOST`, `IMAP_PORT`                         | Mail feature enabled (Infomaniak SMTP/IMAP)              |
| Backups     | `BACKUP_S3_*`, `BACKUP_ENCRYPTION_KEY`                                     | Backups enabled                                          |

### Cross-origin auth variables

These are critical when the API and frontend are on different subdomains
(`api.vollbuild.ch` vs `cos.vollbuild.ch`). See
[SUBDOMAIN_MIGRATION.md](SUBDOMAIN_MIGRATION.md) for the full rationale.

```
CORS_ORIGINS=https://vollbuild.ch,https://cos.vollbuild.ch,http://localhost:5173
JWT_COOKIE_DOMAIN=.vollbuild.ch
JWT_COOKIE_SAMESITE=Lax
JWT_COOKIE_SECURE=true
FRONTEND_BASE_URL=https://cos.vollbuild.ch
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

## Feature flags & limits (`settings.yaml`)

Deployment-time settings at the project root. Override any value at runtime
via environment variables using double-underscore as a nested delimiter:
`FEATURES__MAIL=false`, `LIMITS__MAX_MEMBERS=50`.

```yaml
features:
  polls: true
  events: true
  finance: true
  # Member-facing IMAP inbox — requires Infomaniak SMTP/IMAP configuration.
  mail: true

limits:
  # 0 = unlimited
  max_members: 0
  max_events_per_month: 0
```
