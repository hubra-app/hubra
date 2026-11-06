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
  invoices, cancelling).
- **Changes in manage reach Stripe.** Saving a club's terms in manage
  (All clubs › club › Billing) replaces the subscription's items, with no
  proration, so the new price applies from the next invoice. **Sync with
  Stripe** does the same on demand and reads Stripe's state first. A running
  sponsorship has nothing to charge: the club can't start Checkout and the
  items aren't pushed.
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

## Setting it up

1. **Stripe key.** manage › Payments › Club billing: the key of the Stripe
   account that bills clubs (`billing.stripe.secret_key`, env
   `STRIPE_BILLING_SECRET_KEY`; a secret `sk_` or restricted `rk_` key).
   Left empty, billing uses the Online payments key
   (`payments.stripe.secret_key`). An `sk_test_…` key puts billing in test
   mode (shown in both apps). A restricted key needs write access to
   Customers, Products, Checkout Sessions, Customer portal and
   Subscriptions, and read access to Invoices. The billing account needs no
   Connect.
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
   `STRIPE_BILLING_WEBHOOK_SECRET`). Requests without a valid
   `Stripe-Signature` (HMAC-SHA256, at most 5 minutes old) are refused.
3. **Customer portal.** Settings › Billing › Customer portal in Stripe: turn
   it on, allow updating payment methods and cancelling, and show invoice
   history.
4. **Switch it on.** `billing.enabled` = `on`. Optionally `billing.yearly` =
   `on` for yearly invoices.
5. **Rights.** After the release run `flask seed` and
   `flask sync-permissions`, so admin roles get `billing.billing.manage`.

No database migration is needed: Stripe's ids and state are stored in the
club's settings (`tenants.settings["billing_stripe"]`).

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
| POST | `/api/v1/app/billing/refresh` | Read the subscription from Stripe again (after Checkout) |
| GET | `/api/v1/app/billing/invoices` | The last 12 Stripe invoices with PDF links |

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
