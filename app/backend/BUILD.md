# Backend Prompt: VollBuild — Flask REST API

Build the backend for **VollBuild**, an admin panel for a hobby makerspace / club (members, groups, events, polls, finances, **mail hosting**, settings & roles). This document is the complete spec — implement the whole API from it. A React + Tailwind frontend already exists; the JSON shapes below are taken directly from it, so **match field names exactly** (camelCase as shown) to avoid an adapter layer.

---

## 1. Stack & conventions

- **Python 3.11+, Flask 3.x** using the **application factory** pattern (`create_app(config)`), organized with **Blueprints** (one per module).
- **SQLAlchemy 2.x** (Flask-SQLAlchemy) ORM + **Flask-Migrate** (Alembic) for migrations.
- **Marshmallow** (flask-marshmallow) for request validation + serialization. Reject unknown/invalid fields with 422.
- **JWT auth** via flask-jwt-extended (access + refresh tokens).
- **Flask-CORS** enabled for the frontend origin.
- DB: **SQLite** for dev, **PostgreSQL** for prod (driven by `DATABASE_URL`). No raw SQL — ORM only.
- App runs via `flask run`; production via `gunicorn "hubra:create_app()"`.
- **Pytest** test suite (factory + in-memory SQLite fixtures), **Black** + **Ruff** formatting.
- Config from env vars (`python-dotenv`): `SECRET_KEY`, `JWT_SECRET_KEY`, `DATABASE_URL`, `CORS_ORIGINS`, `ACCESS_TOKEN_MINUTES`, etc. Provide `.env.example`.

### Suggested layout

```
hubra/
  __init__.py            # create_app, extension init, blueprint registration
  config.py              # Dev/Prod/Test configs
  extensions.py          # db, migrate, jwt, ma, cors singletons
  models/                # one module per domain (member.py, group.py, …)
  schemas/               # Marshmallow schemas
  api/                   # blueprints: auth, members, groups, events, finance, mail, settings, dashboard
  services/              # business logic (invoicing, mail simulation, audit)
  seeds.py               # seed demo data (mirrors the frontend fixtures)
  errors.py              # error handlers -> JSON envelope
tests/
migrations/
wsgi.py  .env.example  requirements.txt  README.md
```

---

## 2. Cross-cutting conventions

**Base URL:** `/api/v1`. All responses JSON.

**Success envelope** for collections (the frontend reads `data` + `meta`):

```json
{ "data": [ ... ], "meta": { "page": 1, "perPage": 25, "total": 342 } }
```

Single resources return the bare object.

**Error envelope** (consistent for every 4xx/5xx):

```json
{ "error": { "code": "validation_error", "message": "…", "fields": { "email": "Already in use" } } }
```

Use proper status codes: 200/201/204, 400, 401, 403, 404, 409 (duplicate), 422 (validation), 500.

**List query params (apply consistently):** `?search=`, `?page=`, `?perPage=` (default 25, max 100), `?sort=field` / `-field` (desc), plus per-resource filters noted below. Search is case-insensitive across the resource's text fields.

**IDs:** keep the frontend's human-readable IDs where they exist — members `VB-1042`, invoices `INV-2041` — generated server-side from a sequence. Everything else uses integer or UUID PKs surfaced as strings.

**Timestamps:** persist real `created_at`/`updated_at` (UTC ISO-8601). The frontend currently shows relative/pretty strings (`"2h ago"`, `"Jun 6"`, `"Today 09:42"`) — return BOTH: a raw ISO field (e.g. `joinedAt`) and keep computed display where the UI needs it, or let the frontend format. Prefer returning ISO and a `*Display` convenience string for the trickier ones (mail log time, event date).

**Audit:** every create/update/delete on members, groups, events, finance, roles, mail config writes an **AuditLog** entry (actor, action, target, timestamp). Surfaced via `/settings/audit`.

---

## 3. Auth & users

JWT. Seed an owner user `marco@hubra.club` / `password` (dev only).

| Method | Path | Body | Notes |
| --- | --- | --- | --- |
| POST | `/auth/login` | `{email, password, remember}` | → `{accessToken, refreshToken, user}`. 401 on bad creds. |
| POST | `/auth/refresh` | (refresh token) | → new access token. |
| POST | `/auth/logout` | — | revoke refresh token (blocklist). |
| GET | `/auth/me` | — | current user profile. |
| PATCH | `/auth/me` | `{name, email, …}` | update own profile (user menu → Account settings). |
| POST | `/auth/bootstrap` | see below | first-run setup; only allowed when no club exists yet. |

**Bootstrap** (the 4-step wizard) creates the Club + owner account + initial tiers in one transaction:

```json
{ "club": {"name":"VollBuild Makerspace","city":"Schwyz","type":"makerspace"},
  "account": {"name":"Marco Köhler","email":"marco@hubra.club","password":"…","digest":true},
  "tiers": ["maker","pro","student"] }
```

Returns `{accessToken, user, club}`. After bootstrap, `/auth/bootstrap` returns 409.

**User object:**

```json
{ "id":"u_1","name":"Marco Köhler","email":"marco@hubra.club","role":"owner","avatarColor":"#fece2b","initials":"MK" }
```

**RBAC:** roles `owner > admin > treasurer > lead > member` (see §9). Protect endpoints with a `@require_perm("Finances & invoices")` style decorator that checks the role's permission matrix. Treasurer can touch finances but not roles; leads only their own group/events; etc. Return 403 with the error envelope when denied.

---

## 4. Members  `/members`

Member JSON (mirror exactly):

```json
{
  "id":"VB-1042","name":"Lena Hofer","email":"lena.hofer@mail.ch",
  "tier":"maker","tierName":"Maker","fee":45,"color":"#2596be",
  "group":"Woodshop","cats":["Founding member"],
  "joined":"Mar 2024","joinedAt":"2024-03-12","status":"active",
  "lastSeen":"2h ago","lastSeenAt":"2026-06-08T07:30:00Z","hours":184
}
```

- `status ∈ {active, trial, overdue}`. `tier` FK → Tier (denormalize `tierName/fee/color` into the response). `cats` = many-to-many → Category names. `group` FK → Group name. `hours` = accumulated tool hours.

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/members` | list. Filters: `?status=`, `?tier=`, `?group=`, `?category=`, `?search=` (name/email/id). Paginated. |
| POST | `/members` | create. Body `{name,email,tier,group?,cats?}`. New members default `status:"trial"`. 409 on duplicate email. → audit. |
| GET | `/members/{id}` | full detail (incl. payments, activity, notes — see below). |
| PATCH | `/members/{id}` | partial update (tier, group, status, cats, notes). → audit. |
| DELETE | `/members/{id}` | soft-delete (set `archived`). → audit. |
| GET | `/members/{id}/payments` | payment history → `[{date, amount, method, status}]` (`PAYMENTS` shape; `status:"paid"`). |
| GET | `/members/{id}/activity` | timeline `[{type, title, date, icon}]`. |
| POST | `/members/import` | CSV upload (multipart). Parse, validate rows, bulk-create, return `{created, skipped, errors[]}`. |
| GET | `/members/export` | CSV download of the current filter. |

**Categories** `/categories` (Members ▸ Categories):

```json
{ "id":"founding","name":"Founding member","color":"#2596be","desc":"Joined in the first year — lifetime perks.","count":22 }
```

`count` computed from membership. CRUD: GET list, POST, PATCH, DELETE (block delete if in use → 409, or reassign).

**Applications** `/applications` (Members ▸ Applications, the nav "7" badge):

```json
{ "id":"app_1","name":"…","email":"…","tier":"maker","appliedAt":"…","appliedDisplay":"2d ago" }
```

- GET list (pending only). `POST /applications/{id}/approve` → creates a Member (status trial), removes application, audit, returns the new member. `POST /applications/{id}/decline` → removes, audit. The pending count feeds the sidebar badge.

---

## 5. Groups  `/groups`

```json
{ "id":"wood","name":"Woodshop","color":"#2596be","lead":"Pavel Novák","members":86,"sessions":"Tue & Thu eve","tools":12 }
```

- `members` computed count. `lead` FK → Member. Full CRUD (`@require_perm("…")`; a lead may PATCH only their own group). DELETE blocked if members assigned (→ 409 with a reassign hint). → audit.

---

## 6. Events & Polls

**Events** `/events`:

```json
{ "id":"e1","title":"Open Shop Night","date":"Jun 6","dateAt":"2026-06-06","time":"18:00–22:00",
  "loc":"Main floor","type":"Open shop","going":38,"cap":50,"color":"#2596be" }
```

- `type ∈ {Open shop, Training, Community, Governance, …}` (store as enum/string). `going` = attendee count (could be its own RSVP join table; minimally an integer). CRUD + filter `?type=`. → audit. `GET /events/upcoming?limit=` powers the dashboard.

**Polls** `/polls` (Events ▸ Polls):

```json
{ "id":"p1","q":"New Saturday opening hours?","status":"open","closes":"Jun 12","closesAt":"2026-06-12",
  "total":142,"options":[{"id":"o1","l":"09:00 – 14:00","v":38}, …] }
```

- `status ∈ {open, closed}`; `total` = sum of votes; `v` per option. CRUD for polls + options. `POST /polls/{id}/vote {optionId}` increments a vote (one per member — enforce). Closing a poll sets status. → audit.

---

## 7. Finances

**Overview** `GET /finance/overview` → the dashboard/Finances-overview aggregate:

```json
{ "balance": 48230, "incomeMTD": 11500, "expensesMTD": 9600, "netMTD": 1900,
  "months": [{"m":"Jan","inc":11.2,"exp":9.1}, …],   // FIN_MONTHS, values in CHF thousands
  "openInvoices": {"count":3,"amount":155} }
```

All money in **CHF**. Compute from transactions/invoices, don't hardcode.

**Transactions** `/finance/transactions` (Income & expenses):

```json
{ "id":"t_1","date":"Jun 3","dateAt":"2026-06-03","desc":"Membership dues — May batch",
  "cat":"Dues","type":"income","amt":9420,"method":"TWINT","payee":"…" }
```

- `type ∈ {income, expense}`; `cat` from a fixed set (Dues, Materials, Workshops, Facilities, Grants, Equipment, Other). Filters: `?type=income|expense`, `?cat=`, `?search=`. CRUD ("Record" modal → POST). → audit.

**Invoices** `/finance/invoices`:

```json
{ "id":"INV-2041","member":"Lena Hofer","memberId":"VB-1042","amt":65,
  "issued":"Jun 1","issuedAt":"2026-06-01","due":"Jun 15","dueAt":"2026-06-15","status":"open" }
```

- `status ∈ {paid, open, overdue}` (compute `overdue` from `dueAt < today && unpaid`). CRUD. Actions: `POST /finance/invoices/{id}/remind` (logs a reminder + would enqueue mail → audit, returns ok), `POST /finance/invoices/{id}/pay` (marks paid, creates a matching income transaction, → audit). `POST /finance/invoices/generate` to batch-issue dues for active members.

---

## 8. Mail (hosting — **NOT** marketing campaigns)

This module is **mail-server administration** for the domain `hubra.club`: mailboxes & quota, aliases/forwarders, and a message log for troubleshooting/testing. There are **no campaign / open-rate / CTR concepts** — ignore the legacy `CAMPAIGNS` fixture in the old frontend data; do not build it.

**Mailboxes** `/mail/mailboxes`:

```json
{ "id":"mb_1","addr":"marco@hubra.club","name":"Marco Köhler","used":6.2,"quota":10,
  "msgs":4821,"color":"#2596be","status":"active" }
```

- `used`/`quota` in **GB** (float); `status ∈ {active, send-only}`. CRUD:
  - `POST` body `{local, name, quota}` → addr = `{local}@hubra.club`; reject duplicates (409) and invalid local-parts (422). quota 1–25 GB.
  - `PATCH` quota/name/status; `DELETE` mailbox (block if aliases still deliver to it → 409).
  - `GET /mail/mailboxes/summary` → `{count, usedTotal, quotaTotal, msgsStored, domainStatus:{spf,dkim,dmarc}}` for the stat tiles.

**Aliases & forwarders** `/mail/aliases`:

```json
{ "id":"al_1","alias":"info@hubra.club","dest":["hoi@hubra.club"],"type":"Alias","on":true }
```

- `type ∈ {Alias, Forward, Distribution}`; `dest` = list of recipient addresses. CRUD; `PATCH /mail/aliases/{id}` toggles `on` (enable/pause). Validate recipients exist as mailboxes or are valid external addresses.

**Message log** `/mail/log` (troubleshooting trace — the core "tracking" screen):

```json
{ "id":"ml_1","dir":"in","from":"lieferung@filamentworld.ch","to":"buchhaltung@hubra.club",
  "subj":"Rechnung #4471 — PLA/PETG","time":"Today 09:42","timeAt":"2026-06-08T09:42:00Z",
  "size":"84 KB","sizeBytes":86016,"status":"delivered" }
```

- `dir ∈ {in, out}`; `status ∈ {delivered, bounced, deferred, spam, rejected}`. Filters: `?dir=in|out`, `?status=`, `?search=` (from/to/subject), `?mailbox=`. Paginated, newest first.
- `GET /mail/log/{id}` → full **trace** for the modal: the record plus a `log` array of SMTP transcript lines, e.g.

```json
{ "...": "...", "headers": {...},
  "log": [
    {"t":"09:42:01","stage":"connect","line":"220 mx.hubra.club ESMTP ready"},
    {"t":"09:42:02","stage":"mail-from","line":"250 2.1.0 Ok"},
    {"t":"09:42:03","stage":"data","line":"250 2.0.0 queued as 4A1F2"},
    {"t":"09:42:04","stage":"delivery","line":"250 2.1.5 delivered to buchhaltung"}
  ] }
```

Generate transcript lines appropriate to `status` (bounced → `550 5.1.1 user unknown`, deferred → `451 4.7.1 greylisted`, rejected → `554 5.7.1 rejected by policy`, spam → `250 … quarantined`).

- `POST /mail/log/{id}/redeliver` → appends a new delivery attempt, returns updated trace, → audit.
- `POST /mail/test` body `{from, to, subject}` → simulates sending a test message, **creates a new outbound log entry** (status delivered/bounced based on validity), returns it. This is the "Send test email" action; the result shows up in the log.
- `GET /mail/log/summary` → `{messages24h, deliveredPct, failed, spamBlocked}` stat tiles.
- `GET /mail/domain` / `PATCH /mail/domain` → domain auth status (SPF/DKIM/DMARC) + default from-address + signature (also surfaced in Settings ▸ Mail).

---

## 9. Settings  `/settings`

- **General** `GET|PATCH /settings/general` → club name, city, timezone, currency, public-profile toggle, logo (upload → `/settings/logo`).
- **Tiers** `/settings/tiers` (= membership tiers): `{id,name,fee,color,count}` — CRUD. `count` computed.
- **Roles** `/settings/roles`:

  ```json
  { "id":"treasurer","name":"Treasurer","desc":"Finances, invoices & exports.","members":2,"color":"#ff4d3d","system":false }
  ```

  CRUD for non-system roles (`owner` & `member` are `system:true`, undeletable).
- **Permission matrix** `/settings/permissions`:

  ```json
  { "area":"Finances & invoices","perms":{"owner":true,"admin":false,"treasurer":true,"lead":false,"member":false} }
  ```

  > Rename the legacy `"Mail campaigns"` area to **`"Mail"`** (since the mail module is hosting, not campaigns). Areas: Members, Finances & invoices, Events & polls, Mail, Roles & permissions, Global settings, Audit log. `lead` may carry an `"own"` scope value instead of a bool. `PATCH /settings/permissions` updates a cell; owner column is always-true & locked. This matrix backs the `@require_perm` decorator.
- **Audit log** `GET /settings/audit`:

  ```json
  { "id":"a_1","who":"Marco Köhler","act":"approved application","tgt":"Felix Wagner",
    "t":"Today · 09:42","at":"2026-06-08T09:42:00Z","ic":"check" }
  ```

  Read-only, newest-first, paginated, filter `?actor=` / `?action=`.

---

## 10. Dashboard  `/dashboard`

`GET /dashboard/summary` → everything the overview needs in one call:

```json
{
  "stats": { "activeMembers":342, "memberDelta":18, "netMonth":1900,
             "openInvoices":3, "openInvoicesAmount":155, "upcomingEvents":5 },
  "growth": [212,224,231,240,258,266,279,290,301,318,327,342],
  "upcomingEvents": [ {event} … up to 4 ],
  "posts": [ {"author":"Marco Köhler","color":"#2596be","title":"…","snippet":"…","t":"2h ago","comments":8,"likes":34} … ]
}
```

**Posts** (member feed) can be its own `/posts` resource (GET list + POST) reused here.

**Notifications** `/notifications` (the bell): `GET` list `{id,kind,title,msg,at,read}` with `kind ∈ {info,success,warning,member}`; `POST /notifications/read-all`; unread count in `meta.unread` (feeds the topbar badge).

---

## 11. Data model summary (tables)

`users`, `clubs`, `tiers`, `members`, `categories`, `member_categories` (M2M), `applications`, `groups`, `events`, `event_rsvps`, `polls`, `poll_options`, `poll_votes`, `transactions`, `invoices`, `roles`, `permissions`, `mailboxes`, `aliases`, `alias_recipients`, `mail_log`, `mail_log_lines`, `posts`, `notifications`, `audit_log`, `settings` (singleton/club). Add `created_at`/`updated_at` to all; soft-delete (`archived_at`) on members/groups.

---

## 12. Seeds & tests

- **`seeds.py`** (`flask seed` CLI): load demo data **identical to the frontend fixtures** so the UI lights up immediately — the 4 tiers, 6 categories, 7 groups (`GROUP_DATA`), 18 members (`VB-1042`+), 5 events, 3 polls, 8 transactions, 7 invoices, 5 roles + the permission matrix, 7 audit entries, 3 posts, **6 mailboxes, 6 aliases, 10 message-log entries**, owner user. Use the exact names/colors/values from the frontend's `data.jsx` + `data-ops.jsx` (provided alongside this prompt).
- **Tests:** auth (login/refresh/me/bootstrap-once), members CRUD + duplicate-email 409 + filters + CSV import, application approve→member, invoice pay→transaction, poll vote-once, mailbox quota validation + delete-block, alias toggle, mail test creates a log entry, `/mail/log/{id}` trace lines vary by status, RBAC denials (treasurer blocked from roles, lead limited to own group). Aim for the happy path + the key guard rails on every blueprint.

---

## 13. Deliverables

1. Running Flask app (`flask run`), `create_app` factory, blueprints per §3–10.
2. Models + migrations; `flask seed` populating demo data.
3. Marshmallow validation on every write; consistent success/error envelopes.
4. JWT auth + RBAC decorator driven by the permission matrix.
5. Pytest suite (green) + README (setup, env vars, `flask db upgrade`, `flask seed`, run, test) + `.env.example` + `requirements.txt`.
6. CORS configured for the frontend origin.

Match the JSON field names exactly as specified — the frontend consumes them directly.
