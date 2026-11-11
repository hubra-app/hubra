import { withStepUp } from '@/api/stepUp'
import { apiFetch, apiFetchRaw } from '@hubra/api-client'
import type { PriceUnit } from '@/api/platform'

export interface Tenant {
  id: number
  name: string
  slug: string
  plan: string
  status: string
  settings: Record<string, unknown>
  /** Sandbox club: always on the Stripe sandbox keys. */
  sandbox?: boolean
  created_at: string | null
  updated_at: string | null
  deleted_at: string | null
  usage?: TenantUsage
}

export interface TenantUsage {
  tenant_id: number
  member_count: number
  domain_count: number
  user_count: number
  audit_entry_count: number
  storage_bytes: number
  api_calls_30d: number
  plan: string
  status: string
}

export interface TenantListResponse {
  tenants: Tenant[]
  total: number
  page: number
  per_page: number
}

export interface TenantListParams {
  search?: string
  plan?: string
  status?: string
  sort_by?: string
  sort_dir?: string
  page?: number
  per_page?: number
  include_deleted?: boolean
}

function buildQuery(params: TenantListParams): string {
  const qs = new URLSearchParams()
  if (params.search) qs.set('search', params.search)
  if (params.plan) qs.set('plan', params.plan)
  if (params.status) qs.set('status', params.status)
  if (params.sort_by) qs.set('sort_by', params.sort_by)
  if (params.sort_dir) qs.set('sort_dir', params.sort_dir)
  if (params.page) qs.set('page', String(params.page))
  if (params.per_page) qs.set('per_page', String(params.per_page))
  if (params.include_deleted) qs.set('include_deleted', '1')
  const s = qs.toString()
  return s ? `?${s}` : ''
}

export async function listTenants(
  params: TenantListParams = {},
): Promise<TenantListResponse> {
  return apiFetch<TenantListResponse>(`/platform/system/tenants${buildQuery(params)}`)
}

export async function getTenant(id: number): Promise<{ tenant: Tenant }> {
  return apiFetch<{ tenant: Tenant }>(`/platform/system/tenants/${id}`)
}

export async function createTenant(data: {
  name: string
  slug: string
  plan?: string
  admin_email?: string
  admin_password?: string
  sandbox?: boolean
}): Promise<{ tenant: Tenant; provisioning_status_url: string }> {
  return apiFetch('/platform/system/tenants', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function deleteTenant(
  id: number,
  force = false,
): Promise<{ message: string }> {
  return apiFetch(`/platform/system/tenants/${id}?force=${force ? '1' : '0'}`, {
    method: 'DELETE',
  })
}

export async function disableTenant(id: number): Promise<{ tenant: Tenant }> {
  return apiFetch(`/platform/system/tenants/${id}/disable`, { method: 'POST' })
}

export async function enableTenant(id: number): Promise<{ tenant: Tenant }> {
  return apiFetch(`/platform/system/tenants/${id}/enable`, { method: 'POST' })
}

export async function archiveTenant(id: number): Promise<{ tenant: Tenant }> {
  return apiFetch(`/platform/system/tenants/${id}/archive`, { method: 'POST' })
}

export async function impersonateTenant(
  id: number,
  body: { reason: string; user_id?: number; allow_changes?: boolean; minutes?: number },
): Promise<{
  impersonating: boolean
  tenant_slug: string
  member_id: number
  expires_at: string
  read_only: boolean
}> {
  return withStepUp(() =>
    apiFetch(`/platform/system/tenants/${id}/impersonate`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  )
}

export interface GlobalAuditEntry {
  id: number
  tenant_id: number | null
  actor_id: number | null
  action: string
  target_type: string | null
  target_id: string | null
  details: Record<string, unknown> | null
  ip_address: string | null
  time: string
}

export async function listGlobalAudit(
  params: { page?: number; per_page?: number; id?: number } = {},
): Promise<{ entries: GlobalAuditEntry[]; total: number }> {
  const qs = new URLSearchParams()
  if (params.id) qs.set('id', String(params.id))
  if (params.page) qs.set('page', String(params.page))
  if (params.per_page) qs.set('per_page', String(params.per_page))
  const s = qs.toString()
  return apiFetch(`/platform/system/audit${s ? `?${s}` : ''}`)
}

// ── Audit search across the platform and every club ─────────────────────────

export type AuditSource = 'all' | 'platform' | 'club'

export interface AuditSearchParams {
  q?: string
  source?: AuditSource
  tenant_id?: number
  action?: string
  /** YYYY-MM-DD, inclusive. */
  from?: string
  to?: string
  hide_logins?: boolean
  page?: number
  per_page?: number
}

export interface AuditSearchEntry {
  /** Unique across both logs. */
  key: string
  source: 'platform' | 'club'
  id: number
  tenant_id: number | null
  club: string | null
  time: string | null
  action: string
  actor_id: number | null
  actor: string | null
  actor_email: string | null
  target_type: string | null
  target_id: string | null
  target_label: string | null
  details: unknown
  ip_address: string | null
}

function auditQuery(params: AuditSearchParams) {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === '' || v === false || v === 'all') continue
    qs.set(k, v === true ? '1' : String(v))
  }
  const s = qs.toString()
  return s ? `?${s}` : ''
}

export async function searchAudit(params: AuditSearchParams) {
  return apiFetch<{ entries: AuditSearchEntry[]; total: number; page: number; per_page: number }>(
    `/platform/system/audit/search${auditQuery(params)}`,
  )
}

/** Downloads the search as CSV; returns the rows and whether it was cut. */
export async function exportAudit(params: Omit<AuditSearchParams, 'page' | 'per_page'>) {
  const res = await apiFetchRaw(`/platform/system/audit/export${auditQuery(params)}`)
  if (!res.ok) {
    let message = `HTTP ${res.status}`
    try {
      message = ((await res.json()) as { message?: string }).message ?? message
    } catch {
      /* not JSON */
    }
    throw new Error(message)
  }
  const blob = await res.blob()
  const name =
    /filename=([^;]+)/.exec(res.headers.get('Content-Disposition') ?? '')?.[1] ?? 'hubra-audit.csv'
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
  return {
    rows: Number(res.headers.get('X-Rows') ?? 0),
    truncated: res.headers.get('X-Truncated') === 'true',
  }
}

export interface TenantRequest {
  id: number
  user_id: number
  name: string
  slug: string
  plan: string
  status: string
  admin_note: string | null
  reviewed_by: number | null
  created_at: string | null
  updated_at: string | null
}

export async function listTenantRequests(
  status?: string,
): Promise<{ requests: TenantRequest[] }> {
  const qs = new URLSearchParams()
  if (status) qs.set('status', status)
  const s = qs.toString()
  return apiFetch(`/platform/system/tenant-requests${s ? `?${s}` : ''}`)
}

export async function approveTenantRequest(
  id: number,
): Promise<{
  request: TenantRequest
  tenant: { id: number; name: string; slug: string; plan: string; status: string }
  /** Whether the requester was sent an email about the decision. */
  notified: boolean
}> {
  return apiFetch(`/platform/system/tenant-requests/${id}/approve`, { method: 'POST' })
}

export async function rejectTenantRequest(
  id: number,
  note?: string,
): Promise<{ request: TenantRequest; notified: boolean }> {
  return apiFetch(`/platform/system/tenant-requests/${id}/reject`, {
    method: 'POST',
    body: JSON.stringify({ note }),
  })
}

export interface TenantMember {
  id: number
  user_id: number | null
  name: string
  email: string
  status: string
  roles: string[]
}

export async function listTenantMembers(
  tenantId: number,
): Promise<{ members: TenantMember[] }> {
  return apiFetch<{ members: TenantMember[] }>(
    `/platform/system/tenants/${tenantId}/members`,
  )
}

export async function addTenantMember(
  tenantId: number,
  data: { email?: string; user_id?: number },
): Promise<{ member: TenantMember }> {
  return apiFetch<{ member: TenantMember }>(
    `/platform/system/tenants/${tenantId}/members`,
    {
      method: 'POST',
      body: JSON.stringify(data),
    },
  )
}

export interface MyTenant {
  tenant_id: number
  tenant_slug: string | null
  tenant_name: string | null
  member_id: number | null
  /** Whether I administer this club. */
  admin_level: 'owner' | 'admin' | null
  /** Changes with the club's logo; null without one. */
  logo_version?: string | null
}

export async function getMyTenants(): Promise<{ tenants: MyTenant[] }> {
  return apiFetch<{ tenants: MyTenant[] }>('/global/account/my-tenants')
}

export interface TenantModule {
  code: string
  name: string
  description: string
  required: boolean
  dependsOn: string[]
  enabled: boolean
  switchedOn: boolean
  allowed: boolean
  missingDependencies: string[]
  /** Set when the module comes from a plugin. */
  plugin?: { id: string; name: string; version: string; trust: string }
}

export async function getTenantModules(
  tenantId: number,
): Promise<TenantModule[]> {
  return apiFetch<TenantModule[]>(`/app/features/tenants/${tenantId}`)
}

export async function setTenantModule(
  tenantId: number,
  code: string,
  body: { allowed?: boolean; enabled?: boolean },
): Promise<TenantModule> {
  return apiFetch<TenantModule>(`/app/features/tenants/${tenantId}/${code}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}

// ── Club admins ──────────────────────────────────────────────────────────────

export interface ClubAdmin {
  user_id: number
  member_id: number
  name: string
  email: string
  level: 'owner' | 'admin'
}

export interface ClubAdminsResponse {
  club: { id: number; slug: string; name: string }
  admins: ClubAdmin[]
  /** How the caller may manage this list. */
  access: 'platform' | 'owner' | 'admin'
  canManageOwners: boolean
}

export async function getClubAdmins(tenantId: number) {
  return apiFetch<ClubAdminsResponse>(`/platform/system/tenants/${tenantId}/admins`)
}

/** `reason` is required when platform staff change a club's admins. */
export async function addClubAdmin(
  tenantId: number,
  email: string,
  level: 'owner' | 'admin',
  reason?: string,
) {
  return apiFetch<{ admin: ClubAdmin }>(`/platform/system/tenants/${tenantId}/admins`, {
    method: 'POST',
    body: JSON.stringify({ email, level, reason }),
  })
}

export async function removeClubAdmin(tenantId: number, userId: number, reason?: string) {
  return apiFetch(`/platform/system/tenants/${tenantId}/admins/${userId}`, {
    method: 'DELETE',
    body: JSON.stringify({ reason }),
  })
}

// ── Support sessions (manage › Support-Zugriffe) ─────────────────────────────

export interface SupportPerson {
  id: number
  name: string
  email: string
}

export interface SupportSession {
  id: number
  session: string | null
  tenant_id: number | null
  club: string | null
  staff: SupportPerson | null
  member: SupportPerson | null
  member_id: string | null
  reason: string | null
  mode: 'read' | 'act'
  status: 'active' | 'ended' | 'revoked' | 'expired'
  started_at: string
  expires_at: string
  ended_at: string | null
  minutes: number
  seconds: number
  ended_by: SupportPerson | null
}

export async function listSupportSessions(params: {
  status?: 'active'
  tenant_id?: number
  page?: number
  per_page?: number
}) {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined) qs.set(k, String(v))
  return apiFetch<{
    sessions: SupportSession[]
    total: number
    page: number
    per_page: number
    active: number
  }>(`/platform/system/support-sessions?${qs}`)
}

export async function endSupportSession(session: string) {
  return apiFetch<{ ended: string }>(
    `/platform/system/support-sessions/${encodeURIComponent(session)}/end`,
    { method: 'POST' },
  )
}

// ── Club health (manage › Alle Vereine) ──────────────────────────────────────

export type HealthLevel = 'ok' | 'idle' | 'warning' | 'error'

export interface TenantHealth {
  members: number
  active_members: number
  last_activity: string | null
  storage_bytes: number
  mail: { sent: number; failed: number }
  plugins: number
  alerts: { warning: number; error: number }
  level: HealthLevel
}

export interface TenantWithHealth extends Tenant {
  health: TenantHealth
}

export interface TenantHealthParams {
  search?: string
  plan?: string
  status?: string
  health?: HealthLevel | 'problems'
  sort_by?: string
  sort_dir?: 'asc' | 'desc'
  page?: number
  per_page?: number
}

export async function listTenantsHealth(params: TenantHealthParams = {}): Promise<{
  tenants: TenantWithHealth[]
  total: number
  page: number
  per_page: number
  counts: Record<HealthLevel, number>
  windows: { idle_days: number; mail_days: number; alert_hours: number }
}> {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') qs.set(k, String(v))
  }
  const s = qs.toString()
  return apiFetch(`/platform/system/tenants/health${s ? `?${s}` : ''}`)
}

// ── Usage over time (manage › club › Nutzung) ───────────────────────────────

export type TrendRange = '12w' | '26w' | '12m'
export type TrendMetric =
  | 'logins'
  | 'active_members'
  | 'members'
  | 'new_members'
  | 'events'
  | 'invoices'
  | 'invoice_total'
  | 'mails'

export interface TenantTrends {
  range: TrendRange
  unit: 'week' | 'month'
  /** Start day of each bucket, oldest first; the last one is still running. */
  buckets: string[]
  series: Record<TrendMetric, number[]>
}

export async function getTenantTrends(tenantId: number, range: TrendRange) {
  return apiFetch<TenantTrends>(`/platform/system/tenants/${tenantId}/trends?range=${range}`)
}

// ── Limits (members, mails per month, storage) ───────────────────────────────

export type LimitKind = 'members' | 'mail_month' | 'storage_mb'

export interface LimitRow {
  used: number
  /** null: no limit. */
  limit: number | null
  plan_limit: number | null
  /** The club has its own limit (or its own "no limit"). */
  custom: boolean
  percent: number | null
  level: 'ok' | 'warning' | 'over'
}

/** The largest file the club can upload, in MB. */
export interface FileLimit {
  /** What applies: wanted, capped at the server's ceiling. */
  limit: number
  wanted: number
  source: 'club' | 'plan' | 'default'
  custom: boolean
  plan_limit: number | null
  /** files.max_mb, for plans without their own. */
  default: number
  /** MAX_UPLOAD_MB: no upload is larger. */
  ceiling: number
}

export interface TenantLimits {
  plan: string
  warn_percent: number
  limits: Record<LimitKind, LimitRow>
  file?: FileLimit
}

export async function getTenantLimits(tenantId: number) {
  return apiFetch<TenantLimits>(`/platform/system/tenants/${tenantId}/limits`)
}

/** A number, null for no limit, or "plan" to follow the plan again. */
export async function setTenantLimits(
  tenantId: number,
  values: Partial<Record<LimitKind, number | null | 'plan'>> & { file_mb?: number | 'plan' },
) {
  return apiFetch<TenantLimits>(`/platform/system/tenants/${tenantId}/limits`, {
    method: 'PUT',
    body: JSON.stringify(values),
  })
}

// ── Early access per club ────────────────────────────────────────────────────

export interface TenantEarlyAccess {
  early_access: boolean
  features: {
    key: string
    title_de: string
    title_en: string
    stage: 'off' | 'early' | 'all'
    /** The club's own choice; null follows the stage. */
    override: boolean | null
    on: boolean
  }[]
}

export async function getTenantEarlyAccess(tenantId: number) {
  return apiFetch<TenantEarlyAccess>(`/platform/system/tenants/${tenantId}/early-access`)
}

export async function setTenantEarlyAccess(
  tenantId: number,
  body: { early_access?: boolean; features?: Record<string, boolean | null> },
) {
  return apiFetch<TenantEarlyAccess>(`/platform/system/tenants/${tenantId}/early-access`, {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}

// ── Billing terms and Stripe Billing (docs/billing.md) ──────────────────────

/** Stripe's subscription statuses, plus "none" for a club that is not billed. */
export type BillingStatus =
  | 'none'
  | 'trialing'
  | 'active'
  | 'past_due'
  | 'unpaid'
  | 'canceled'
  | 'incomplete'
  | 'paused'

export interface BillingAddon {
  code: string
  label: string
  /** Per unit: once, per member or per licence. */
  price_chf: string
  unit: PriceUnit
}

/** One module the club pays for (or gets with its plan), with its quantity. */
export interface BillingModuleLine {
  code: string
  label: string
  source: 'plan' | 'addon'
  unit: PriceUnit
  unit_price_chf: string
  quantity: number
  /** Comes with the plan at no extra cost. */
  included: boolean
  total_chf: string
}

export interface BillingTerms {
  status: BillingStatus
  trial_ends: string | null
  period_end: string | null
  /** The club's own price per month; null: the plan's list price. */
  price_chf: string | null
  discount_percent: number
  sponsored: boolean
  sponsor_name: string
  sponsored_until: string | null
  sponsor_note: string
  addons: BillingAddon[]
  /** Licences per module code (for prices per licence; 1 if not set). */
  licenses: Record<string, number>
  note: string
  /** Hubra fee in % on the club's online member payments; null: the default. */
  payments_fee_percent: number | null
}

export interface TenantBilling extends BillingTerms {
  /** The platform's default fee on online payments (manage › Payments), null without a key. */
  payments_fee_default: number | null
  plan: string
  plan_price_chf: string | null
  base_chf: string
  discount_chf: string
  addons_chf: string
  module_lines: BillingModuleLine[]
  /** Members counted, when a price is per member. */
  members: number | null
  total_chf: string
  due_chf: string
  sponsorship_running: boolean
  sponsorship_days_left: number | null
  sponsorship_ending_soon: boolean
  sponsorship_ended: boolean
  trial_days_left: number | null
  /** Stripe's side: ids, its status, and whether billing is on at all. */
  stripe: TenantStripeState
}

export interface TenantStripeState {
  enabled: boolean
  testMode: boolean
  customer_id?: string
  subscription_id?: string
  /** Stripe's own subscription status (may differ from the terms' status). */
  status?: string
  current_period_end?: string | null
  cancel_at_period_end?: boolean
  payment_failed_at?: string | null
  updated_at?: string
  /** Set when saving the terms could not push them to Stripe. */
  error?: string
}

export interface BillingOverview {
  enabled: boolean
  testMode: boolean
  yearly: boolean
  mrrChf: string
  arrChf: string
  payingClubs: number
  perStatus: Partial<Record<BillingStatus, number>>
  trouble: {
    id: number
    name: string
    slug: string
    status: BillingStatus
    dueChf: string
    paymentFailedAt: string | null
    periodEnd: string | null
  }[]
}

/** Read the club's subscription from Stripe and push the terms to it. */
export async function syncTenantBilling(tenantId: number) {
  return apiFetch<TenantBilling>(`/platform/system/tenants/${tenantId}/billing/sync`, {
    method: 'POST',
  })
}

export async function getBillingOverview() {
  return apiFetch<BillingOverview>('/platform/system/billing/overview')
}

export async function getTenantBilling(tenantId: number) {
  return apiFetch<TenantBilling>(`/platform/system/tenants/${tenantId}/billing`)
}

export async function setTenantBilling(tenantId: number, values: Partial<BillingTerms>) {
  return apiFetch<TenantBilling>(`/platform/system/tenants/${tenantId}/billing`, {
    method: 'PATCH',
    body: JSON.stringify(values),
  })
}

// ── Plans a club can be on (manage › Einstellungen › Tarife) ─────────────────

export interface PlanChoice {
  key: string
  name_de: string
  name_en: string
  public: boolean
  hidden: boolean
  price_month_chf: string | null
  modules: { code: string; price_chf: string | null; unit: PriceUnit }[]
}

export interface PlanChoices {
  plans: PlanChoice[]
  addons: {
    code: string
    name: string
    price_month_chf: string | null
    price_unit: PriceUnit
  }[]
}

export async function listPlanChoices() {
  return apiFetch<PlanChoices>('/platform/system/plans')
}

export async function setTenantPlan(id: number, plan: string) {
  return apiFetch<{ tenant: Tenant }>(`/platform/system/tenants/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ plan }),
  })
}

// ── Data protection requests (copy or deletion of someone's data) ────────────

export type DataRequestKind = 'export' | 'deletion'
export type DataRequestStatus = 'open' | 'done' | 'rejected'

export interface DataRequest {
  id: number
  tenant_id: number
  tenant_name: string
  kind: DataRequestKind
  status: DataRequestStatus
  subject_name: string
  subject_email: string
  member_id: number | null
  received_on: string
  received_via: string
  due_on: string
  days_left: number | null
  overdue: boolean
  due_soon: boolean
  note: string
  created_at: string | null
  created_by: number | null
  created_by_name: string | null
  handled_at: string | null
  handled_by: number | null
  handled_by_name: string | null
  outcome: string
  result: {
    rows?: Record<string, number>
    exported_at?: string
    deleted?: boolean
    deleted_at?: string
    kept_without_name?: { invoices: number; transactions: number }
  } | null
  exports: { at: string; by: number }[]
}

export interface DataRequestList {
  requests: DataRequest[]
  counts: { open: number; overdue: number }
}

export async function listDataRequests(params: {
  status?: DataRequestStatus | 'all'
  tenant_id?: number
}) {
  const q = new URLSearchParams()
  if (params.status) q.set('status', params.status)
  if (params.tenant_id) q.set('tenant_id', String(params.tenant_id))
  return apiFetch<DataRequestList>(`/platform/system/data-requests?${q}`)
}

export async function createDataRequest(
  tenantId: number,
  body: {
    kind: DataRequestKind
    subject_name?: string
    subject_email?: string
    member_id?: number | null
    received_on?: string
    received_via?: string
    note?: string
  },
) {
  return apiFetch<DataRequest>(`/platform/system/tenants/${tenantId}/data-requests`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function updateDataRequest(
  id: number,
  body: Partial<Pick<DataRequest, 'subject_name' | 'subject_email' | 'member_id' | 'note'>>,
) {
  return apiFetch<DataRequest>(`/platform/system/data-requests/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

/** Downloads the member's data as a JSON file (asks for the password again). */
export async function downloadDataExport(req: DataRequest) {
  const data = await withStepUp(() =>
    apiFetch<unknown>(`/platform/system/data-requests/${req.id}/export`, { method: 'POST' }),
  )
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `daten-${req.tenant_id}-${req.member_id}.json`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export async function deleteDataRequestMember(id: number, confirm: string) {
  return withStepUp(() =>
    apiFetch<DataRequest>(`/platform/system/data-requests/${id}/delete-member`, {
      method: 'POST',
      body: JSON.stringify({ confirm }),
    }),
  )
}

export async function closeDataRequest(id: number, status: 'done' | 'rejected', outcome: string) {
  return apiFetch<DataRequest>(`/platform/system/data-requests/${id}/${status}`, {
    method: 'POST',
    body: JSON.stringify({ outcome }),
  })
}

/** Make the club a sandbox club (Stripe sandbox keys only) or a normal one.
 * A running subscription in the old Stripe mode ends at once; a club that
 * paid live gets a sandbox subscription with the same lines. */
export interface SandboxSwitchResult {
  tenant: Tenant
  /** The subscription in the old mode was ended. */
  subscriptionEnded: boolean
  /** A sandbox subscription was started in its place. */
  sandboxSubscription: boolean
}

export async function setTenantSandbox(tenantId: number, sandbox: boolean): Promise<SandboxSwitchResult> {
  return apiFetch<SandboxSwitchResult>(`/platform/system/tenants/${tenantId}/sandbox`, {
    method: 'PUT',
    body: JSON.stringify({ sandbox }),
  })
}
