# API Overview

All endpoints live under `https://api.hubra.club/api/v1/`. In production, an
external Traefik terminates TLS and routes `api.hubra.club` directly to the
Flask backend (`backend:5000`). Caddy is not in the API path.

For the complete endpoint reference, see [`app/backend/API.md`](../app/backend/API.md).

## Auth scheme — JWT-in-cookies

Authentication uses **JWT access and refresh tokens stored in HttpOnly cookies**,
not `Authorization: Bearer` headers. Tokens are never exposed to JavaScript.

| Cookie                  | HttpOnly | Purpose                          |
| ----------------------- | -------- | -------------------------------- |
| `access_token_cookie`   | Yes      | Short-lived access token (15 min)|
| `refresh_token_cookie`  | Yes      | Long-lived refresh token (30 d)  |
| `csrf_access_token`     | No       | CSRF double-submit (JS-readable) |
| `csrf_refresh_token`    | No       | CSRF double-submit (JS-readable) |

All cookies use `Domain=.hubra.club`, `SameSite=Lax`, `Secure` (HTTPS only),
`Path=/`. See [SUBDOMAIN_MIGRATION.md](SUBDOMAIN_MIGRATION.md) for the full
cookie/CORS rationale.

### Auth flow

```
POST /api/v1/auth/login     { "email": "...", "password": "..." }
  → 200  { "mustChangePassword": false, "member": { ... } }
  → Set-Cookie: access_token_cookie=...; HttpOnly; Secure; Domain=.hubra.club; SameSite=Lax
  → Set-Cookie: refresh_token_cookie=...; HttpOnly; Secure; Domain=.hubra.club; SameSite=Lax
  → Set-Cookie: csrf_access_token=...; Secure; Domain=.hubra.club; SameSite=Lax
  → Set-Cookie: csrf_refresh_token=...; Secure; Domain=.hubra.club; SameSite=Lax

POST /api/v1/auth/refresh   (refresh cookie sent automatically)
  + X-CSRF-TOKEN: <csrf_refresh_token cookie value>
  → 200  { "ok": true }
  → Set-Cookie: access_token_cookie=... (rotated)

POST /api/v1/auth/logout    (access cookie sent automatically)
  + X-CSRF-TOKEN: <csrf_access_token cookie value>
  → 204  (cookies cleared)
```

### CSRF protection

State-changing requests (`POST`, `PUT`, `PATCH`, `DELETE`) must include an
`X-CSRF-TOKEN` header whose value matches the `csrf_access_token` cookie
(double-submit pattern). `GET` requests do not require the header. The CSRF
header is in the CORS `Access-Control-Allow-Headers` list.

### Cross-origin requests

The frontend and API are on different subdomains (`app.hubra.club` vs
`api.hubra.club`), so every frontend request must send credentials:

- `fetch` → `credentials: 'include'`
- `axios` → `withCredentials: true`

Without this, cookies are not sent and every call returns 401.

CORS is owned by Flask (not Traefik). The allowlist is configured via
`CORS_ORIGINS` (comma-separated, no wildcards). Preflight `OPTIONS` returns
200/204 with CORS headers and is exempt from auth and rate limiting. All CORS
responses include `Vary: Origin` so shared caches don't cross-serve headers.

## Blueprints

| Blueprint         | Base path                | Key endpoints                                                                                                                                                    |
| ----------------- | ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Auth**          | `/api/v1/auth/`          | `login`, `refresh`, `logout`, `forgot-password`, `reset-password`, `bootstrap`, `bootstrap-status` (public)                                                     |
| **Account**       | `/api/v1/account/`       | `GET /` (profile), `PATCH /` (update), `change-password`, `permissions`, `sessions`, `devices`, `invoices`, `groups`, `mail-settings`, `verify-email`           |
| **Members**       | `/api/v1/members/`       | `GET /`, `POST /`, `GET /<id>`, `PATCH /<id>`, `DELETE /<id>`, `archive`, `unarchive`, `disable`, `enable`, `provision`, `set-password`, `export`, `count`      |
| **Groups**        | `/api/v1/groups/`        | `GET /`, `POST /`, `GET /<id>`, `PATCH /<id>`, `DELETE /<id>`, `GET /<id>/members`, `POST /<id>/members/<mid>`, `DELETE /<id>/members/<mid>`, `count`            |
| **Finance**       | `/api/v1/finance/`       | Transactions CRUD, transaction-categories CRUD, invoices CRUD, `bulk`, `remind`, `overview`, external-parties CRUD, `qr-bill.pdf`                               |
| **Mail**          | `/api/v1/mail/`          | Mailboxes, addresses, aliases, system-addresses, member-mail provisioning, group/function mail, `test`, `reconcile`                                             |
| **Applications**  | `/api/v1/applications/`  | `GET /`, `GET /<id>`, `approve`, `decline`, `DELETE /<id>` (people ask to join on SSO)                                                                              |
| **Events**        | `/api/v1/events/`        | CRUD, `POST /<id>/attendees/<mid>`, `DELETE /<id>/attendees/<mid>`                                                                                               |
| **Polls**         | `/api/v1/polls/`         | CRUD, `vote`, `close`, `remind`                                                                                                                                  |
| **Posts**         | `/api/v1/posts/`         | CRUD, `comments`, `like`                                                                                                                                         |
| **Functions**     | `/api/v1/functions/`     | CRUD, `holders` (assign/remove)                                                                                                                                  |
| **Tiers**         | `/api/v1/tiers/`         | CRUD, `members`, `calculate-cost`                                                                                                                                |
| **Roles**         | `/api/v1/roles/`         | CRUD, `GET /<id>/permissions`, `PUT /<id>/permissions`                                                                                                           |
| **Settings**      | `/api/v1/settings/`      | Key-value settings CRUD, `revert`                                                                                                                                |
| **Features**      | `/api/v1/features/`      | `GET /`, `PUT /<key>`, per-feature settings                                                                                                                      |
| **Bindings**      | `/api/v1/bindings/`      | CRUD, `keys`, `toggle`, `preview`, `registry`, `sources`, `validators`                                                                                          |
| **Notifications** | `/api/v1/notifications/` | `GET /`, `DELETE /<id>`, `PATCH /<id>/read`, `read-all`, `POST /` (create)                                                                                       |
| **Audit**         | `/api/v1/audit/`         | `GET /`, `GET /<id>`                                                                                                                                             |
| **Inventory**     | `/api/v1/inventory/`     | Items CRUD, `instructions`                                                                                                                                      |
| **i18n**          | `/api/v1/i18n/`          | `languages`, per-locale CRUD, `import`, `export`, `copy-defaults`, `duplicate`, `flagged`, `report`                                                             |
| **Codes**         | `/api/v1/codes/`         | CRUD (Fernet-encrypted access codes)                                                                                                                             |
| **Backups**       | `/api/v1/manager/platform/backups/` (global permission `backups.manage`) | `GET /` (`?tenant_id=`), `POST /` (`{tenant_id}` for a club), `GET /<id>`, `DELETE /<id>`, `verify`, `restore` (`{confirm: slug}`), `config`                                                                                               |
| **Platform**      | `/api/v1/manager/platform/` (global permissions `platform.diagnostics`, `platform.settings`) | `settings`, `mail/test`, `health`, `permissions`, `mail-server` (live list of the shared WildDuck, `DELETE /<type>/<id>` orphans, `reconcile`) |
| **Dashboard**     | `/api/v1/dashboard/`     | `summary` (aggregated counts)                                                                                                                                    |
| **System**        | `/api/v1/system/`        | `permissions` (catalog)                                                                                                                                          |
| **Health**        | `/api/v1/`               | `GET /health` (public, cached; details under Platform above)                                                                                                    |
| **Version**       | `/api/v1/`               | `GET /version`, `GET /version/changelog`                                                                                                                        |
| **Setup**         | `/api/v1/setup/`         | `status`, `complete`                                                                                                                                             |

## Permissions

Endpoints use `@permission_required(resource, action, display_name)` decorators.
The permission key is derived as `<blueprint>.<resource>.<action>` (e.g.
`members.members.read`). Admin roles (`is_admin=True`) bypass all permission
checks and receive `permissions: ["*"]`.

Run `flask sync-permissions` to populate the Permission table from decorated
routes. See [`app/backend/API.md`](../app/backend/API.md) for the full catalog.

| Key pattern                | Description                                        |
| -------------------------- | -------------------------------------------------- |
| `members.members.read`     | View members                                       |
| `members.members.create`   | Create members                                     |
| `members.members.update`   | Edit members                                       |
| `members.members.delete`   | Delete members                                     |
| `members.members.export`   | Export member data                                 |
| `finance.transactions.*`   | Transaction CRUD                                   |
| `finance.invoices.*`       | Invoice CRUD, bulk, remind                         |
| `mail.mailboxes.*`         | Mailbox and alias management                       |
| `applications.*.approve`   | Review and approve membership applications         |
| `settings.settings.*`      | Settings read/write                                |
| `audit.audit.read`         | View audit log                                     |

## Response conventions

| Method           | Status | Body                                                          |
| ---------------- | ------ | ------------------------------------------------------------- |
| `GET` (list, paginated) | `200` | `{ "data": [...], "total": N, "page": P, "pageSize": S, "totalPages": T }` |
| `GET` (list, simple)    | `200` | `[...]` (array directly)                                      |
| `GET` (single)         | `200` | Serialized resource object                                    |
| `POST` (create)        | `201`  | Full serialized resource                                      |
| `PATCH` (update)       | `200`  | Full updated resource                                         |
| `DELETE`               | `204`  | Empty                                                         |

Error responses follow `{ "error": "ERROR_CODE", "message": "..." }`.
