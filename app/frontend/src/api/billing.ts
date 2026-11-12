import { apiFetch } from '@hubra/api-client'

/** What the club pays Hubra and its Stripe subscription (docs/billing.md). */
export type HubraBillingStatus =
  | 'none'
  | 'trialing'
  | 'active'
  | 'past_due'
  | 'unpaid'
  | 'canceled'
  | 'incomplete'
  | 'paused'

export interface HubraModuleLine {
  code: string
  label: string
  source: 'plan' | 'addon'
  unit: string
  unit_price_chf: string
  quantity: number
  included: boolean
  total_chf: string
}

export interface HubraBilling {
  plan: string
  status: HubraBillingStatus
  trial_ends: string | null
  period_end: string | null
  plan_price_chf: string | null
  base_chf: string
  discount_percent: number
  discount_chf: string
  addons_chf: string
  module_lines: HubraModuleLine[]
  members: number | null
  total_chf: string
  due_chf: string
  sponsored: boolean
  sponsor_name: string
  sponsored_until: string | null
  sponsorship_running: boolean
  sponsorship_days_left: number | null
  sponsorship_ending_soon: boolean
  trial_days_left: number | null
  /** Billing through Stripe is on for the platform. */
  enabled: boolean
  testMode: boolean
  /** Charged once a year (12 months at once) instead of monthly. */
  yearly: boolean
  /** Something is due and the club can start paying. */
  canPay: boolean
  /** Hubra's fee in % on online member payments (Online payments plugin), null without it. */
  paymentsFeePercent: number | null
  stripe: {
    hasCustomer: boolean
    hasSubscription: boolean
    status: string | null
    currentPeriodEnd: string | null
    cancelAtPeriodEnd: boolean
    paymentFailedAt: string | null
  }
}

export interface HubraInvoice {
  id: string
  number: string | null
  created: string | null
  status: string | null
  totalChf: string
  paid: boolean
  url: string | null
  pdf: string | null
}

export async function getHubraBilling(): Promise<HubraBilling> {
  return apiFetch('/app/billing/')
}

/** A Stripe Checkout page that starts the subscription. */
export async function startHubraCheckout(): Promise<{ url: string }> {
  return apiFetch('/app/billing/checkout', { method: 'POST' })
}

/** Stripe's customer portal: card, address, invoices, cancel. */
export async function openHubraPortal(): Promise<{ url: string }> {
  return apiFetch('/app/billing/portal', { method: 'POST' })
}

/** Cancel the subscription: it runs to the end of the paid period, then ends. */
export async function cancelHubraSubscription(): Promise<HubraBilling> {
  return apiFetch('/app/billing/cancel', { method: 'POST' })
}

/** Take a cancellation back before the period ends. */
export async function resumeHubraSubscription(): Promise<HubraBilling> {
  return apiFetch('/app/billing/resume', { method: 'POST' })
}

/** Read Stripe again, after coming back from Checkout. */
export async function refreshHubraBilling(): Promise<{ stripe: HubraBilling['stripe'] }> {
  return apiFetch('/app/billing/refresh', { method: 'POST' })
}

export async function listHubraInvoices(): Promise<{ items: HubraInvoice[] }> {
  return apiFetch('/app/billing/invoices')
}

/** Where Hubra's invoices go. Until the club saves its own, taken from the
 * club's finance email and the address of its QR bills (`own: false`). */
export interface HubraBillingContact {
  email: string
  street: string
  houseNo: string
  postalCode: string
  city: string
  country: string
  own: boolean
}

export async function getHubraBillingContact(): Promise<HubraBillingContact> {
  return apiFetch('/app/billing/contact')
}

/** Saves the billing email and address; Stripe gets them at once. */
export async function saveHubraBillingContact(
  body: Omit<HubraBillingContact, 'own'>,
): Promise<HubraBillingContact> {
  return apiFetch('/app/billing/contact', { method: 'PUT', body: JSON.stringify(body) })
}

/** A plan the club can pick (public, its current one, or a custom plan
 *  manage offered to this club). */
export interface HubraPlanChoice {
  key: string
  name_de: string
  name_en: string
  description_de: string
  description_en: string
  price_month_chf: string | null
  price_year_chf: string | null
  features: { de: string; en: string }[]
  modules: {
    code: string
    name_de: string
    name_en: string
    price_chf: string | null
    unit: string
    included: boolean
    /** Key of the lower plan the module comes from; null: the plan's own. */
    inherited_from: string | null
  }[]
  /** The plan includes every module of this plan too; null: stands alone. */
  builds_on: string | null
  /** Not public: manage offered it to this club. */
  custom: boolean
  limits: { members: number | null; mail_month: number | null; storage_mb: number | null }
  highlighted: boolean
}

/** A paid module: with the plan, taken by the club, or offered. */
export interface HubraAddonOffer {
  code: string
  name_de: string
  name_en: string
  note_de: string
  note_en: string
  plugin: string | null
  price_month_chf: string | null
  unit: 'flat' | 'member' | 'license'
  /** included: free with the plan; plan: the plan adds it at its price;
   *  addon: the club took it; null: offered. */
  source: 'included' | 'plan' | 'addon' | null
  licenses: number | null
  /** Members holding a licence (modules priced per licence). */
  holders: { id: number; name: string }[] | null
}

export interface HubraCatalog {
  plan: string
  /** A sponsor pays the club's subscription: nothing on the prices is charged. */
  sponsorship: { running: boolean; name: string; until: string | null }
  /** False while a sponsor pays or the club is not billed. */
  billed: boolean
  members: number
  plans: HubraPlanChoice[]
  addons: HubraAddonOffer[]
}

/** Plans and paid modules with prices (every member may read it). */
export async function getHubraCatalog(): Promise<HubraCatalog> {
  return apiFetch('/app/billing/catalog')
}

export async function chooseHubraPlan(plan: string): Promise<HubraBilling> {
  return apiFetch('/app/billing/plan', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan }),
  })
}

export async function setHubraAddon(
  code: string,
  body: { on?: boolean; licenses?: number },
): Promise<HubraBilling> {
  return apiFetch(`/app/billing/addons/${encodeURIComponent(code)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

/** Give a licensed module's licences to exactly these members. */
export async function setHubraLicenseHolders(
  code: string,
  memberIds: number[],
): Promise<{ code: string; holders: { id: number; name: string }[] }> {
  return apiFetch(`/app/billing/licenses/${encodeURIComponent(code)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ memberIds }),
  })
}

export type LimitKind = 'members' | 'mail_month' | 'storage_mb'

export interface LimitRow {
  used: number
  limit: number | null
  percent: number | null
  level: 'ok' | 'warning' | 'over'
}

/** GET /app/billing/limits: usage against the limits, the member grace period and the plan that fits. */
export interface HubraLimits {
  plan: string | null
  limits: Record<LimitKind, LimitRow>
  warn_percent: number
  grace_days: number
  /** When new members stop joining at the member limit (ISO); null without a grace period. */
  grace_until: string | null
  suggestion: {
    key: string
    name_de: string
    name_en: string
    price_month_chf: string | null
    limits: Record<LimitKind, number | null>
  } | null
  code: 'LIMIT_NEAR' | null
}

export async function getHubraLimits(): Promise<HubraLimits> {
  return apiFetch('/app/billing/limits')
}
