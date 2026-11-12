# Billing clubs for Hubra (Stripe Billing)

Hubra charges each club for its plan and paid add-ons through the
platform's Stripe account, with Stripe Billing. This is separate from the
**Online payments** plugin, where members pay their club through the club's
own Stripe account (Stripe Connect).

Code: `app/backend/hubra/core/billing/` (Stripe client and service),
`hubra/api/billing/routes.py` (club routes and webhook), the platform routes
in `hubra/api/tenant/routes.py`, and the hourly task in
`hubra/core/tasks/billing_tasks.py`. The terms themselves (plan, own price,
discount, sponsor, add-ons) are in `hubra/core/services/club_billing.py`, as
before.

## What it does

- **One Stripe subscription per club.** Its items are built from the club's
  terms: one line for the plan (base price after discount) and one per paid
  module or add-on. Prices are sent inline (`price_data`, CHF) on products
  with fixed ids (`hubra_plan_<plan>`, `hubra_module_<code>`), so nothing has
  to be set up in Stripe by hand. With `billing.yearly` on, a line costs
  12 × the monthly price, charged once a year.
- **Clubs pay themselves.** Admins with the right `billing.billing.manage`
  see **Settings › Hubra subscription** in the club app: plan, lines,
  discount, sponsor, what is due, the next invoice and Stripe's invoices.
  **Pay now** opens Stripe Checkout (mode `subscription`); during a trial
  that ends at least two days ahead, the subscription starts with
  `trial_end` set to the trial's end, so nothing is charged before.
  **Manage payment** opens Stripe's customer portal (card, billing address,
  invoices). **Cancel subscription** asks first, then sets
  `cancel_at_period_end`: the subscription runs to the end of the period
  already paid (or of the trial) and then ends, and the club's status
  follows to *canceled*. Until then **Take cancellation back** undoes it.
  This works whatever the portal's settings are (hubra#260).
- **Changes reach Stripe, pro rata.** Saving a club's terms in manage
  (All clubs › club › Billing), a club changing its plan or add-ons, and
  the hourly member count update only the subscription items that changed,
  with `create_prorations` (see "Changes during the month"). **Sync with
  Stripe** does the same on demand and reads Stripe's state first.
- **Sponsored and not-billed clubs pay nothing.** While a sponsorship runs,
  or while manage has the club on status *none* (not billed), there is
  nothing to charge: the club can't start Checkout. A subscription that
  already runs is set to end at the end of the period already paid
  (`cancel_at_period_end`, Mike's choice 2026-11-12), so nothing more is
  charged; if the sponsorship ends (or billing starts again) before that,
  the cancellation is taken back and the items are updated as usual. After
  the subscription has ended, the club pays again through Checkout. The
  club app says who covers the cost instead of "next invoice"
  (`GET /app/billing/catalog` has `sponsorship` and `billed`).
- **Stripe's state is followed.** The webhook and an hourly reconcile
  (`reconcile-billing-hourly`, minute 35) copy the subscription's status,
  period end and trial end into the club's terms. Stripe's
  `incomplete_expired` counts as `canceled`.
- **Payment problems are visible.** When a subscription becomes
  `past_due`, `unpaid` or `incomplete`, or an invoice payment fails, manage
  gets the platform alert **A club payment failed** (alert type `billing`,
  set its channels under Alerts › Rules). The club sees a red notice on its
  subscription tab. Settings › Plans & prices in manage shows monthly and
  yearly revenue, clubs per status and the clubs with payment problems.

Not built yet: putting a club into read-only mode after it stays unpaid,
and Stripe Tax / VAT on the invoices.

## Who the subscription belongs to

The customer in Stripe is **the club**, not the person who pays. Each
Hubra club (tenant) has at most one Stripe customer and one running
subscription, and every invoice belongs to that customer.

| In Stripe | Comes from | Set when |
| --- | --- | --- |
| Customer name | the club's name (`tenant.name`) | the first **Pay now** |
| Customer email | the club's billing email (Settings › Hubra subscription › Billing details), else the email of the club admin who clicked **Pay now** | the first **Pay now**, and on every save of the billing details |
| Customer address | the club's billing address (same place) | the first **Pay now**, and on every save of the billing details; Checkout also asks for it |
| Customer metadata | `tenant_id` and `slug` of the club | the first **Pay now** |
| Customer language | the club's locale (default `de-CH`) | the first **Pay now** |
| Subscription metadata | `tenant_id` | Checkout |
| Checkout `client_reference_id` | `tenant_id` | Checkout |
| Card | what the admin types in Checkout or the portal | Checkout, portal |

Hubra stores the customer id and the subscription id in the club's
settings (`tenants.settings["billing_stripe"]`). The webhook finds the club
by `tenant_id` in the metadata (or `client_reference_id`) and, failing
that, by the stored customer id. Any admin of the club with the right
`billing.billing.manage` opens the same customer in Checkout and the
portal, so it doesn't matter which admin pays. The email is where Stripe
sends invoices and receipts.

**Billing details in Hubra.** Settings › Hubra subscription has a
**Billing details** card (email for invoices, street, number, postal code,
city, country). Until the club saves it, it is filled in from the club's
finance email (`Club.Contact.FinanceEmail`) and the address of its QR bills
(`Club.Banking.*`). Saving stores it on the club
(`tenants.settings["billing_contact"]`) and, if the club already has a
Stripe customer, updates that customer's email and address at once, so the
next invoice uses them. API: `GET` / `PUT /api/v1/app/billing/contact`
(`billing.billing.manage`).

Checkout also always asks for a billing address
(`billing_address_collection: required`), prefilled, and writes what the
admin confirms to the customer (`customer_update[address]: auto`). The
customer's name stays the club's name: the name typed in Checkout is the
cardholder's and is not copied. Clubs can also edit the address in the
portal if **Customer information** is turned on in Stripe's portal
settings; a later save in Hubra overwrites it again.

To find a club in the Stripe dashboard: manage › All clubs › club ›
Billing shows the customer and subscription ids, or search Stripe for the
club's name or `metadata['slug']:'<slug>'`.

Good to know: the customer's name is copied once. Renaming the club in
Hubra does not rename the Stripe customer, so change it in Stripe (or the
portal) as well. The same goes for line names: a product is named once
(`Hubra <plan>`, `Hubra <add-on label>`) when Hubra first uses it.

**What the test invoice shows.** With an `sk_test_…` key, Checkout,
invoices and the portal carry Stripe's test-mode badge, and the test card
`4242 4242 4242 4242` pays. The first invoice is made when Checkout
completes:

- To: the club's name, its billing address and its billing email (or the
  admin's).
- From: the Stripe account's public name, address and invoice footer (see
  [Which Stripe account](#which-stripe-account)).
- One line `Hubra <plan>` (plan price after the club's discount), plus one
  line `Hubra <add-on>` per paid module or add-on with its quantity
  (1, members or licences) and unit price, in CHF, for the coming month
  (or year with `billing.yearly`).
- During a trial: an invoice of CHF 0.00 now, and the first real one on the
  day the trial ends.

The club sees the same invoices (number, date, total, paid, PDF link) in
Settings › Hubra subscription. The portal shows the club's card, billing
address, the invoice history and the next payment date. Cancelling is in
Hubra itself (*Cancel subscription*); the portal may offer it too,
depending on its settings.

## Changes during the month

Stripe bills a subscription **in advance**: each invoice charges the
coming period (month or year). The billing day is the day Checkout was
completed, or the day the trial ended.

When the terms change in the middle of a period (manage, the club on its
subscription tab, or the member count), Hubra updates only the items that
changed, with `proration_behavior: create_prorations` (Mike's choice,
2026-11-06):

- **The rest of the period is charged pro rata on the next invoice.** An
  add-on taken on day 10 of a 30-day month adds a line "Remaining time on
  Hubra <add-on>" for 20/30 of its price, plus its full price for the new
  period. Nothing is charged at once; no extra invoice.
- **A removal or a lower count gives a pro-rata credit** on the next
  invoice ("Unused time on …").
- **Per-member prices follow the member count.** The hourly reconcile
  pushes the new quantity when it changed: a member who joins mid-month
  costs the rest of that month pro rata, a member who leaves is credited.
  Only the quantity of that item changes, so the other lines show no
  credit and recharge.
- **A plan change** works the same way: the price difference for the rest
  of the period goes on the next invoice.
- **During a trial** Stripe doesn't prorate: changes just set what the
  first real invoice charges.
- **Yearly billing** (`billing.yearly`): the same, pro rata over the year.

The club's subscription tab shows the new amount at once; Stripe's
dashboard shows the prorations under **Upcoming invoice**. Charging at once
instead is `always_invoice` in `sync()` (`hubra/core/billing/service.py`).

## What a club changes itself

Settings › Hubra subscription (permission `billing.billing.manage`):

- **Breakdown:** plan, discount, each paid module with its quantity
  ("84 members × 0.20", "3 licences × 5.00"), what the plan includes, and
  the total per month.
- **Plan:** the plans every club can pick (manage › Settings › Plans,
  *Clubs can pick it*, `selectable`), the current one, and **custom
  plans** manage offered to this club. Whether a plan is on the website
  (*On the website*, `public`) is a separate switch: a plan can be on the
  pricing page but only given by hand, or selectable without being
  advertised. A switch
  is refused (409 `PLAN_TOO_SMALL`) when the club has more members than
  the plan allows. Other private plans stay manage's to give.
- **Add-on modules:** modules with a public list price (manage › Plans ›
  Add-ons) and those on the club's bill. Taking one switches the module
  on, dropping it switches it off (data stays). Modules priced per licence
  get a licence count. A price manage agreed with the club stays.
- **Settings › Modules** shows each paid module's price; switching on a
  module the club doesn't pay yet asks first and books it.

**Licences.** A module priced per licence (an add-on with unit
`license`, or a module the plan adds at a per-licence price) is billed for
`licenses[code]` licences, and the club gives each licence to a member
(*Zuweisen* next to the module; `PUT /api/v1/app/billing/licenses/<code>`,
`hubra/core/services/licenses.py`). **Only holders may use the module:** the
module gate answers everyone else `403 LICENSE_REQUIRED`, and `GET
/api/v1/modules/` marks the module `licensed: false` for them so their
navigation hides it. Rights still apply on top: a holder needs the
module's permissions as before.

- Holders are stored on the club (`tenants.settings["license_holders"]`,
  `{code: [member id]}`), at most as many as licences (409
  `TOO_MANY_HOLDERS`). If manage lowers the count, the first holders keep
  theirs.
- A licensed module with no holders is closed to everyone until the club
  assigns licences, so assign them right after booking.
- Modules included at no cost, or priced flat or per member, need no
  licence.

**Plans that build on each other.** In manage › Settings › Plans a plan
can optionally *build on* another plan (`builds_on`). It then includes
every module of that plan, and of the plan that one builds on, plus its
own: Starter includes A and B, Growth builds on Starter and adds C, so
Growth has A, B and C. A change to the lower plan reaches the plans above
it. When both plans list the same module, the higher plan's own entry (and
price) counts. Plans without it stand alone, as before. A plan others
build on cannot be deleted (409 `PLAN_IS_BASE`). The plan cards, the
club's plan picker ("Everything in Starter, plus …"), the breakdown,
licences and the public price list all use the full module list; each
inherited module says which plan it comes from (`inherited_from`).

**Custom plans.** A plan that is not selectable can list clubs (`club_ids`,
*Custom plan for these clubs* on the plan form). Those clubs see it in
Settings › Hubra subscription, marked *For your club*, and can switch to
it themselves; other clubs and the website never see it.

## Hubra fee on online payments

With the **Online payments** plugin, members pay their club through the
club's own Stripe account. Hubra can take a fee in percent on each of those
payments, the Hubra fee (a Stripe application fee, paid to the Payments
platform account, not to the billing account). It is not Stripe's fee: Stripe
charges the club its own fees on top.

- **Default for all clubs:** manage › Payments (`payments.fee_percent`).
- **Per club:** manage › All clubs › club › Billing › *Hubra fee on
  online payments* (`payments_fee_percent` in the club's terms, 0–10 %).
  Empty uses the default; `0` means no fee for that club. A club can, for
  example, get a lower subscription price and a higher fee instead.

The fee applies to checkouts started after the change. The club sees it on
Settings › Hubra subscription when it is above 0.

By default the club pays both fees: the member pays the invoice amount and
Stripe's fee and the Hubra fee come off what the club receives. In the
plugin (Weitere › Online-Zahlungen › Einstellungen › *Wer zahlt die Gebühren*, payments
1.1.0) the club can pass them on: it enters its Stripe rate and members pay
a surcharge sized so the club still receives the full invoice amount,
`(invoice + fixed) / (1 − Stripe % − Hubra %)`, rounded up.

## Setting it up

1. **Stripe keys.** manage › Payments › Club billing: the keys of the
   Stripe account that bills clubs, one live (`billing.stripe.secret_key`,
   `sk_live_`/`rk_live_`, env `STRIPE_BILLING_SECRET_KEY`) and one sandbox
   (`billing.stripe.sandbox_secret_key`, `sk_test_`/`rk_test_`). Left empty,
   billing uses the Online payments key of the same mode. Which one is used
   follows the **Stripe mode** (see "Sandbox and live" below). A restricted
   key needs write access to Customers, Products, Checkout Sessions,
   Customer portal and Subscriptions, and read access to Invoices. The
   billing account needs no Connect.
2. **Webhook.** In the Stripe dashboard (Developers › Webhooks) add an
   endpoint `https://<your API host>/api/v1/global/billing/stripe/webhook`
   with the events:
   - `checkout.session.completed`
   - `customer.subscription.created`, `customer.subscription.updated`,
     `customer.subscription.deleted`
   - `invoice.paid`, `invoice.payment_failed`

   In Stripe's form: scope **Your account**, payload style **Snapshot**;
   the API version can stay at the newest. Hubra reads subscriptions again
   with its own pinned version, so newer payloads don't matter.

   Copy its signing secret (`whsec_…`) into manage › Payments › Club billing
   (`billing.stripe.webhook_secret`, or the env var
   `STRIPE_BILLING_WEBHOOK_SECRET`). Add the same webhook in the Stripe
   sandbox too and store its secret as `billing.stripe.sandbox_webhook_secret`.
   Requests without a valid `Stripe-Signature` (HMAC-SHA256, at most 5
   minutes old, either secret) are refused.
3. **Customer portal.** Settings › Billing › Customer portal in Stripe: turn
   it on, allow updating payment methods, the billing address and email,
   and cancelling, and show invoice history.
4. **Switch it on.** `billing.enabled` = `on`. Optionally `billing.yearly` =
   `on` for yearly invoices.
5. **Rights.** After the release run `flask seed` and
   `flask sync-permissions`, so admin roles get `billing.billing.manage`.

No database migration is needed: Stripe's ids and state are stored in the
club's settings (`tenants.settings["billing_stripe"]`, and
`billing_stripe_sandbox` for the sandbox).

## Sandbox and live

Online payments and billing each have a **live** and a **sandbox** key. The
platform setting `stripe.mode` (manage › Payments, Sandbox or Live) picks
which set the clubs use:

- **Sandbox** (the default): every club uses the sandbox keys. No real money
  moves; both apps show "test mode".
- **Live**: clubs use the live keys. **Sandbox clubs** stay on the sandbox
  keys.

A **sandbox club** is a demo or test club: manage › club › Sandbox club (or
"Sandbox club" when creating it; `PUT /api/v1/platform/system/tenants/<id>/sandbox`).
It always uses the sandbox keys for Online payments and its Hubra
subscription, and manage's revenue figures leave it out (counted as
`sandboxClubs`). When the switch changes the club's Stripe mode, a running
subscription in the old mode **ends at once** (no proration, no last
invoice), so it never runs on unseen. A club that paid live and becomes a
sandbox club gets a **sandbox subscription** with the same lines, billed by
invoice (`collection_method=send_invoice`, no card needed). A sandbox club
made live again has no subscription and starts paying through Checkout,
like a new club (hubra#260). The answer says what happened
(`subscriptionEnded`, `sandboxSubscription`), and the audit entry records it.

Stripe's ids are kept per mode (`tenants.settings["billing_stripe"]` live,
`["billing_stripe_sandbox"]` sandbox), so switching never mixes test and
live customers. A webhook event from the other mode than the club's
(`livemode`) is ignored, so a sandbox event can't change a real club. The
payments plugin likewise uses the club's connected account of the current
mode only (from version 1.2.0); after going live a club connects its Stripe
account once more.

Each slot only takes a key of its mode (`sk_live_` in the live slot,
`sk_test_` in the sandbox slot). A test key stored in a live slot before
there were two keeps working as the sandbox key, and is never used live.

### Privacy policy and terms of service

Stripe asks for Hubra's privacy policy and terms of service URLs (dashboard:
Settings › Public details, and Connect › Platform profile for the Connect
platform). Use the same addresses as the platform settings `legal.privacy_url`
and `legal.terms_url` (manage › Platform › Legal pages; defaults
https://hubra.club/datenschutz/ and https://hubra.club/nutzungsbedingungen/).
Hubra links them itself on sign-up, in the footers (`GET /api/v1/instance`
returns them as `legal`) and above the pay button of Stripe Checkout.

## Which Stripe account

Hubra is not a registered company yet. Until it is, the seller is
**BitsAndBricks** (Mike's sole proprietorship), and Hubra is its product:
"Hubra, powered by BitsAndBricks". Billing has its own key
(`billing.stripe.secret_key`), so it can run in a Stripe account of its
own, apart from the Connect platform of Online payments.

Use a **separate Stripe account for Hubra under the BitsAndBricks login**
(Stripe: Account switcher › New account, same legal entity), not the
BitsAndBricks account itself. Same owner, same verification, but Hubra keeps
its own customers, subscriptions, webhooks, payouts and branding, and that
account can later move to a Hubra company on its own.

Settings for that account:

| Where in Stripe | Value |
| --- | --- |
| Public business name | `Hubra` |
| Statement descriptor (max 22) | `HUBRA BITSANDBRICKS` |
| Shortened descriptor | `HUBRA` |
| Support email / URL | Hubra's support address, `https://hubra.club` |
| Branding (Checkout, portal, invoices) | Hubra logo and violet |
| Invoice footer | "Hubra is a product of BitsAndBricks" plus the legal name and address |

The legal name and address on invoices and on the website imprint stay
BitsAndBricks (with the owner's full name, as a sole proprietorship must
show it).

Things to know (checked against Stripe's pages on 2026-11-06):

- Stripe accepts sole proprietors / individuals, not only companies.
- TWINT through Stripe is **B2C only**. A club is a legal entity, so paying
  for Hubra counts as B2B: offer card payments, and ask Stripe Support
  before turning TWINT on for subscriptions (it would also need a newer
  pinned API version in `hubra/core/billing/stripe_api.py`). Members paying
  their club with the Online payments plugin is B2C and can use TWINT.

When Hubra becomes a company:

- Change the legal entity of the Hubra Stripe account. Moving an account
  to a new legal entity goes through Stripe Support; ask them first what
  happens to customers, subscriptions and saved cards.
- Change the invoice footer, imprint and the descriptor
  (e.g. `HUBRA.CLUB`). Hubra's code needs no change: the key, the webhook
  secret and the stored customer and subscription ids stay valid as long as
  the account stays the same. A new account instead needs a new key, a new
  webhook and a migration of customers and payment methods by Stripe.

## API

Club app (`billing.billing.manage`):

| Method | Path | What |
| --- | --- | --- |
| GET | `/api/v1/app/billing/` | Terms the club may see, `enabled`, `testMode`, `yearly`, `canPay`, `stripe` (status, period end, cancel at period end, last failed payment) |
| POST | `/api/v1/app/billing/checkout` | `{url}` of a Stripe Checkout page (409 `ALREADY_SUBSCRIBED`, 400 `NOTHING_TO_PAY`, 503 `BILLING_OFF`) |
| POST | `/api/v1/app/billing/portal` | `{url}` of Stripe's customer portal (409 `NO_CUSTOMER`) |
| POST | `/api/v1/app/billing/cancel` | Cancel: the subscription runs to the end of the paid period (or the trial), then ends; answers like `GET /` (409 `NO_SUBSCRIPTION`) |
| POST | `/api/v1/app/billing/resume` | Take the cancellation back while the period runs (409 `NO_SUBSCRIPTION`) |
| POST | `/api/v1/app/billing/refresh` | Read the subscription from Stripe again (after Checkout) |
| GET | `/api/v1/app/billing/invoices` | The last 12 Stripe invoices with PDF links |
| GET | `/api/v1/app/billing/catalog` | Plans the club can pick and paid modules with prices; any member (the modules page shows prices) |
| PUT | `/api/v1/app/billing/plan` | `{plan}`: switch to a plan the club may pick (400, 409 `PLAN_TOO_SMALL`) |
| PUT | `/api/v1/app/billing/licenses/<code>` | `{memberIds}`: the members who hold the module's licences (409 `TOO_MANY_HOLDERS`, 404 not licensed) |
| PUT | `/api/v1/app/billing/addons/<code>` | `{on?, licenses?}`: take or drop a paid module, set its licences (404 not offered, 409 `IN_PLAN`, 403 `MODULE_BLOCKED`) |

Platform (manage):

| Method | Path | Right | What |
| --- | --- | --- | --- |
| GET | `/api/v1/platform/system/tenants/<id>/billing` | `tenants.read` | Terms plus `stripe` (ids, Stripe's status) |
| PATCH | `/api/v1/platform/system/tenants/<id>/billing` | `tenants.update` | Change terms; pushes them to Stripe, a Stripe error comes back as `stripe.error` |
| POST | `/api/v1/platform/system/tenants/<id>/billing/sync` | `tenants.update` | Read Stripe, push the terms (409 `NO_SUBSCRIPTION`) |
| GET | `/api/v1/platform/system/billing/overview` | `tenants.read` | Revenue, clubs per status, payment problems |

Stripe: `POST /api/v1/global/billing/stripe/webhook` (signed by Stripe, no
sign-in). A Stripe error while handling an event answers 502, so Stripe
sends the event again.
