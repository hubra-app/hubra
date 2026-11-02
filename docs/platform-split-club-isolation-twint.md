# Platform backend, per-club backends and TWINT

Status: recommendation, nothing built. Written 2026-11-02 against main `3a776cc`.

This answers three questions:

1. Should platform work (platform operations, support, maintenance) run in
   its own backend, apart from normal club traffic?
2. Should a club be able to get its own backend and database?
3. Can we take TWINT through Stripe, and would a separate TWINT provider be
   better?

Short answers:

1. **Yes, but as a second deployment of the same image, not a new
   codebase.** A `platform` role serves the manage APIs and runs platform
   jobs on its own Celery queue, with its own host, its own database role
   and tighter network access. About 0.5 to 1 GB of RAM more, no new
   service to maintain.
2. **Not now.** Schema-per-club already gives each club its own data,
   backups and restore. A fully separate stack per club costs roughly
   1.5 GB of RAM and an update/migration run per club, and breaks "one
   account for all clubs" unless SSO is federated. Offer it later as a
   paid "dedicated install" for clubs or federations that need it by
   contract; keep the mail stack shared.
3. **Stripe supports TWINT, including subscriptions** (since API version
   `2026-05-27.dahlia`), for Swiss and most European Stripe accounts, CHF
   only. The catch: Stripe lists TWINT as **B2C only**, and Hubra billing
   clubs is B2B. Use cards (and invoices) for the platform subscription, and
   use TWINT where it fits: members paying their club. For that, Stripe
   Connect is the simplest single integration; Payrexx is cheaper per
   payment and Swiss, and is the alternative worth keeping open.

---

## 1. Dedicated platform backend

### How it works today

One backend image runs three processes: the API (gunicorn), the Celery
worker and Celery beat (see [scaling.md](scaling.md)). All of them serve
every kind of request:

| Kind | Where it lives today | Who calls it |
| --- | --- | --- |
| Club app | `/api/v1/members`, `/events`, `/finance`, ... (module blueprints) | Members, club admins, via `app.hubra.club` |
| Accounts / SSO | `/api/v1/auth`, `/api/v1/account` | Everyone, via `sso.hubra.club` / `join.hubra.club` |
| Club admin in manage | `/api/v1/system/tenants/...` (`api/tenant/routes.py`, ~49 routes) | Club owners/admins and staff, via `manage.hubra.club` |
| Platform | `/api/v1/manager/platform` (~33 routes), `/manager/platform/backups` (~7), `/manager/plugins` (~20), `/api/v1/admin` (~9) | Staff only |

All of it is one Flask app on `api.hubra.club`, one Postgres database
(`public` schema for accounts and platform tables, one `tenant_<id>` schema
per club, chosen by `search_path`), one Redis, and one Celery queue.

Security work already in place that a split builds on: platform routes only
accept the dedicated account token, not a club token
(`require_global_permission`, PR #103), dangerous actions need a step-up
(password/TOTP/passkey), staff need 2FA, and the app connects with the
restricted `POSTGRES_APP_USER` role (PR #106).

### What the split buys

- **Blast radius.** A bug or exploit in club code (most of the code, most of
  the traffic, most of the plugins) can't reach plugin upload, backups,
  restore, key rotation or impersonation, because those routes simply don't
  exist in the club pods.
- **Separate access.** The platform host can sit behind an IP allowlist, a
  VPN/Tailscale or Cloudflare Access, with stricter rate limits, without
  touching the member experience.
- **Operations don't starve clubs, and vice versa.** A large restore, a
  backup run or a plugin install runs on platform workers; a burst of
  invoice mails on the 1st doesn't delay a health alert.
- **Separate deploys** (optional): you can roll the platform side first and
  watch it before members get the new version.

### Options

| | A. Same image, `platform` role (recommended) | B. Separate queues only | C. Separate service/codebase |
| --- | --- | --- | --- |
| What changes | Env `HUBRA_ROLE=platform\|club\|all` decides which blueprints and beat entries load; new host; new queue; new DB role | Platform jobs go to a `platform` Celery queue with their own worker | New repo/service with its own models and API |
| Isolation | Routes, workers, network and DB rights | Workers only | Full |
| Code work | Medium (routing table, two DB roles, ingress, manage API base URL) | Small | Large; models and migrations would be duplicated or shared as a package |
| Extra cost | ~0.5–1 GB RAM (1 API pod + 1 worker) | ~256–512 MB (1 worker) | Same as A plus a second codebase to maintain |
| Default for Compose installs | `HUBRA_ROLE=all` keeps today's single container | Unchanged | Two services required |

**B is the first step of A**, so it can ship on its own and pays off
immediately.

### What would move (option A)

**API routes served only by the platform role**

- `/api/v1/manager/platform/*` (settings, mail relays, alerts, maintenance,
  Discord log, diagnostics, builds, encryption key rotation)
- `/api/v1/manager/platform/backups/*` (backup, check, restore)
- `/api/v1/manager/plugins/*` (upload, confirm, install, update)
- `/api/v1/admin/*`
- `/api/v1/system/*` (all clubs, club health, club requests, club admin,
  quotas, support sessions/impersonation)

**Stay in the club role:** all module blueprints, `/api/v1/auth`,
`/api/v1/account`, `/api/v1/plugins` (plugin assets), health and version.

**Open question:** `/api/v1/system` is not staff-only. Club owners use it
from manage (club admin view of `/api/v1/system/tenants/<id>`), people
starting a club post `/system/tenant-requests` from `join.hubra.club`, and
`/system/impersonation/stop` is called while a support session is open in
the club app. Two ways:

- Serve all of `/system` from the platform role, and put only the
  staff-only paths (`/manager/*`, `/admin/*`, the all-clubs, health,
  request review and impersonation paths of `/system`) behind the allowlist
  with ingress path rules. Simple, and club owners keep working
  from anywhere. **Recommended.**
- Move the club-owner endpoints to the club role. Cleaner, but it splits
  manage's API across two hosts.

**Celery queues**

| Queue `platform` (platform worker) | Queue `club` (club workers) |
| --- | --- |
| backups (daily/weekly/monthly + manual), restores | invoices, recurring bookings, statements, overdue reminders |
| health-check, infra-checks, api-error-rate, check-upgrades | event and poll reminders, web push, notifications |
| check-domains, check-mail-relays, mailbox quota, quota checks | WildDuck mail sync and reconcile, IMAP inbox plugin |
| plugin-updates, plugin install tasks, platform Discord log/audit | Discord bot work for clubs, role sync |
| prune platform events, session/blocklist cleanup | club mail sending |

Celery `task_routes` sends each task to its queue; one beat keeps sending
all scheduled jobs (the slot claims and advisory locks in
`core/tasks/scheduling.py` still apply).

### Sharing the database

Same Postgres, same migrations, same image, so no schema drift. The split
is in **rights**, not in data:

- `hubra_app` (club pods): today's restricted role, minus write access to
  platform-only tables (`platform_settings`, backup records, plugin tables,
  key material, platform events) where club code doesn't need it. It keeps
  read access where club code reads platform settings (mail relay, limits).
- `hubra_platform` (platform pods): today's rights plus what backups,
  restores and schema provisioning need (`CREATE SCHEMA`, rename schema for
  restore).
- Migrations keep running from one init job with the owner role.

This needs one audit pass over which tables club code writes, because some
platform tables are written as side effects (for example platform events
from club actions). Those stay writable or move behind a small insert-only
function.

### Sharing auth

Nothing new is needed: both roles verify the same JWT keys and read the
same session/blocklist tables. The account token cookie is already set for
`.hubra.club`, so it reaches a new `platform-api.hubra.club` (or
`manage-api.hubra.club`) host. Platform routes keep refusing club tokens and
keep the step-up. The manage frontend gets its own API base URL; CORS on the
platform host only allows `manage.hubra.club`.

### Cost

On the current k3s setup (backend limits 1 CPU / 512 MiB per pod), option A
adds one API pod and one worker pod, about 0.5–1 GB RAM and almost no CPU at
rest. On the existing VPS that fits without a bigger plan; I didn't check
the node's free memory. Compose installs keep `HUBRA_ROLE=all` and pay
nothing.

### Suggested order

1. Celery queues + a second worker (option B). Small, no API change.
2. `HUBRA_ROLE` blueprint filter, new host, manage API base URL, ingress
   allowlist on the staff paths.
3. Split DB roles after the table audit.

---

## 2. Dedicated backend per club

### Today

Every club already has its own Postgres schema (`tenant_<id>`), its own
encryption key (PR #86), its own backup and restore (`pg_dump --schema`),
its own limits (PR #138) and its own maintenance gate. What it shares:
compute (API and worker pods), the Postgres server, Redis, the mail stack
and the account/SSO data in `public`.

### Options

| | A. Shared (today) | B. Own database, shared app | C. Own pods, shared DB | D. Own full stack ("dedicated install") |
| --- | --- | --- | --- | --- |
| Data isolation | Schema | Database (or server) | Schema | Everything |
| Noisy neighbours | Shared | Compute shared | DB shared | None |
| Code change | None | Large: one engine per club, migrations per DB, cross-DB joins with `public` (accounts, memberships) must go | Medium: club needs its own API host to route by; custom domains aren't served yet | Small for the app (it's a normal install); large if accounts must stay shared with hubra.club |
| Accounts | One account for all clubs | Same | Same | Separate accounts unless SSO is federated (OIDC) |
| Updates | One migration run | One migration run per club DB | One | One per club, versions can drift |
| Backups | Per schema (today) | Per DB, simpler | Per schema | Per install, fully separate |
| Extra cost per club | – | ~100–300 MB RAM per DB if on the shared server, more for own server | ~0.5–1 GB RAM | ~1.5–2 GB RAM (API, worker, beat, Postgres, Redis) plus ops time |

The RAM numbers are estimates from the current pod limits and typical
Postgres/Redis footprints, not measurements.

### Mail stack

Keep it shared in every option. WildDuck, Haraka, ZoneMTA and MongoDB per
club would multiply the heaviest part of the system, and each would need
its own sending IP reputation, PTR record, DKIM keys and port 25 handling.
Per-club separation for mail already exists where it matters: own domains
and own mailboxes, with the platform relay and fallback relay in front. A dedicated install
(option D) can point at the shared hubra.club mail stack over SMTP/API or
use an external relay.

### When it is worth it

- A contract requires it: a federation, canton or large association that
  needs data on its own server, its own backups, or a separate legal
  processor setup.
- One club is so large that its load hurts others. That is better solved
  first with limits, queues and more replicas.
- A club wants to self-host. That already works today: it is a normal
  Compose or k3s install of the same images (see
  [run-with-docker.md](run-with-docker.md)).

### Recommendation

Stay on A. Offer D later as a paid "dedicated" plan, deployed as its own
Flux Kustomization per customer with a fixed release channel, and decide
then whether its accounts stay separate (simplest) or sign in through
hubra.club SSO (needs OIDC, a real project). B and C cost almost as much
work as D with less benefit.

---

## 3. TWINT billing

There are two different "billings" in Hubra, and TWINT fits them
differently:

- **Platform billing:** Hubra charges clubs (base plan + add-ons). You
  chose Stripe Billing for this; nothing is built yet.
- **Member payments:** clubs collect fees from members. On the roadmap as
  `twint-payments` in `app/backend/ROADMAP.yaml`; today members pay by
  QR-bill and the club books it.

### What Stripe supports (checked 2026-11-02)

From [Stripe's TWINT page](https://docs.stripe.com/payments/twint) and the
[May 2026 changelog](https://docs.stripe.com/changelog/dahlia/2026-05-27/recurring-payments-twint):

- **Account country:** CH, LI, the EU/EEA countries and GB can accept
  TWINT. A Swiss Stripe account works.
- **Customers:** Swiss TWINT users only. **Currency CHF only.**
- **Amounts:** CHF 0.50 to CHF 5,000 per payment.
- **Subscriptions: supported** since API version `2026-05-27.dahlia`:
  Billing subscriptions and invoices, Checkout in `setup` and
  `subscription` mode, PaymentIntents with
  `setup_future_usage=off_session`, SetupIntents. The customer approves a
  mandate once in their TWINT app; later charges are off-session.
- **One active mandate per merchant and customer.** A new one revokes the
  old (`payment_intent_mandate_revoked_mandate_collision`). Customers can
  revoke the mandate in their app at any time.
- **Products:** Billing, Invoicing, Customer Portal, Checkout, Payment
  Element and Connect are supported; Terminal and the Express Checkout
  Element are not. No manual capture.
- **Refunds** up to 180 days, full and partial. Disputes are possible.
- **Activation:** request it in the Dashboard. The `twint_payments`
  capability stays `pending` until TWINT checks the website: public, prices
  in CHF, legal name, legal form, address, terms, contact.
- **Business model: B2C only (B2B is marked as not supported).**
- **Fee:** 1.9% + CHF 0.30 per payment
  ([Stripe CH pricing](https://stripe.com/en-ch/pricing/local-payment-methods)).

### Platform billing (Hubra → clubs)

A club buying Hubra is a business customer, so it falls under B2B, which
Stripe lists as not supported for TWINT. Using it anyway risks the
capability being refused or withdrawn later.

**Recommendation:** run the platform subscription on cards, with Stripe
invoices as the fallback for clubs that want to pay by bank transfer. Ask
Stripe support whether billing associations (Vereine) counts as B2B before
switching TWINT on; if they say yes, adding it is a Dashboard setting plus
CHF prices, no extra code.

### Member payments (club → members)

This is B2C and the natural place for TWINT. The money must go to the club,
not to Hubra, so it needs either a payment platform (Hubra connects each
club's account) or each club bringing its own provider account.

| | Stripe Connect | Payrexx (each club's own account) | Direct TWINT contract |
| --- | --- | --- | --- |
| TWINT fee | 1.9% + CHF 0.30 | 1.25–1.30% + CHF 0.18–0.30, by plan ([pricing](https://payrexx.com/en-ch/pricing)) | 1.3% for QR stickers ([TWINT](https://www.twint.ch/en/business-customers/twint-fees/)); online needs a PSP anyway |
| On CHF 50 | CHF 1.25 | CHF 0.81–0.95 | – |
| Recurring | Yes (mandates) | Yes, "Recurring payments (Subscriptions)" ([docs](https://docs.payrexx.com/merchant/english/payment-provider/payrexx-pay/payment-methods/twint)) | – |
| Max amount | CHF 5,000 | CHF 20,000 | – |
| Club onboarding | In Hubra via Connect onboarding (KYC by Stripe) | Club signs up at Payrexx, pastes API keys into Hubra | – |
| Same integration as platform billing | Yes | No, second provider | – |
| Other | Cards, Apple/Google Pay in the same flow | Swiss company, 50% off plans for recognised charities | – |

**Stripe Connect details that matter:** use direct charges (or
`on_behalf_of`) so each club is the merchant of record. Otherwise Hubra is
the merchant for every club, and because TWINT allows one mandate per
merchant and customer, a member of two clubs would have one club's mandate
revoked by the other's.

**Recommendation:** build member payments behind a small provider
interface (create payment, webhook marks the invoice paid), and start with
**Stripe Connect** so there is one provider for both billings and the club
setup happens inside Hubra. Add a Payrexx adapter if clubs push back on the
fee; the difference is about CHF 0.30–0.45 on a CHF 50 fee.

### What I could not verify

- Whether Stripe treats Hubra billing Vereine as B2B for TWINT. The docs
  only say "B2B ✗"; ask Stripe support.
- Whether Payrexx offers a platform/partner API that lets Hubra onboard
  clubs the way Stripe Connect does. Its public pages don't say; the table
  assumes each club brings its own account.
- Payrexx plan prices per month (the pricing page doesn't show them
  without JavaScript); only the per-payment fees are confirmed.
- Whether Stripe charges anything extra for Connect on top of 1.9% + CHF
  0.30 under the pricing model you would pick.
- Whether a TWINT mandate can be used for a yearly fee that is higher than
  the first payment without the member approving again. The docs say the
  mandate has no fixed amount or schedule, which suggests yes, but I didn't
  test it.
