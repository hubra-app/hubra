import { withStepUp } from '@/api/stepUp'
import { apiFetch, apiFetchRaw } from '@hubra/api-client'

export interface Tenant {
  id: number
  name: string
  slug: string
  plan: string
  status: string
  settings: Record<string, unknown>
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
  return apiFetch<TenantListResponse>(`/system/tenants${buildQuery(params)}`)
}

export async function getTenant(id: number): Promise<{ tenant: Tenant }> {
  return apiFetch<{ tenant: Tenant }>(`/system/tenants/${id}`)
}

export async function createTenant(data: {
  name: string
  slug: string
  plan?: string
  admin_email?: string
  admin_password?: string
}): Promise<{ tenant: Tenant; provisioning_status_url: string }> {
  return apiFetch('/system/tenants', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function deleteTenant(
  id: number,
  force = false,
): Promise<{ message: string }> {
  return apiFetch(`/system/tenants/${id}?force=${force ? '1' : '0'}`, {
    method: 'DELETE',
  })
}

export async function disableTenant(id: number): Promise<{ tenant: Tenant }> {
  return apiFetch(`/system/tenants/${id}/disable`, { method: 'POST' })
}

export async function enableTenant(id: number): Promise<{ tenant: Tenant }> {
  return apiFetch(`/system/tenants/${id}/enable`, { method: 'POST' })
}

export async function archiveTenant(id: number): Promise<{ tenant: Tenant }> {
  return apiFetch(`/system/tenants/${id}/archive`, { method: 'POST' })
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
    apiFetch(`/system/tenants/${id}/impersonate`, {
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
  return apiFetch(`/system/audit${s ? `?${s}` : ''}`)
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
    `/system/audit/search${auditQuery(params)}`,
  )
}

/** Downloads the search as CSV; returns the rows and whether it was cut. */
export async function exportAudit(params: Omit<AuditSearchParams, 'page' | 'per_page'>) {
  const res = await apiFetchRaw(`/system/audit/export${auditQuery(params)}`)
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
  return apiFetch(`/system/tenant-requests${s ? `?${s}` : ''}`)
}

export async function listMyTenantRequests(): Promise<{ requests: TenantRequest[] }> {
  return apiFetch('/system/tenant-requests/mine')
}

export async function createTenantRequest(data: {
  name: string
  slug: string
  plan?: string
}): Promise<{ request: TenantRequest }> {
  return apiFetch('/system/tenant-requests', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function approveTenantRequest(
  id: number,
): Promise<{
  request: TenantRequest
  tenant: { id: number; name: string; slug: string; plan: string; status: string }
  /** Whether the requester was sent an email about the decision. */
  notified: boolean
}> {
  return apiFetch(`/system/tenant-requests/${id}/approve`, { method: 'POST' })
}

export async function rejectTenantRequest(
  id: number,
  note?: string,
): Promise<{ request: TenantRequest; notified: boolean }> {
  return apiFetch(`/system/tenant-requests/${id}/reject`, {
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
    `/system/tenants/${tenantId}/members`,
  )
}

export async function addTenantMember(
  tenantId: number,
  data: { email?: string; user_id?: number },
): Promise<{ member: TenantMember }> {
  return apiFetch<{ member: TenantMember }>(
    `/system/tenants/${tenantId}/members`,
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
  return apiFetch<{ tenants: MyTenant[] }>('/account/my-tenants')
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
  return apiFetch<TenantModule[]>(`/features/tenants/${tenantId}`)
}

export async function setTenantModule(
  tenantId: number,
  code: string,
  body: { allowed?: boolean; enabled?: boolean },
): Promise<TenantModule> {
  return apiFetch<TenantModule>(`/features/tenants/${tenantId}/${code}`, {
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
  return apiFetch<ClubAdminsResponse>(`/system/tenants/${tenantId}/admins`)
}

/** `reason` is required when platform staff change a club's admins. */
export async function addClubAdmin(
  tenantId: number,
  email: string,
  level: 'owner' | 'admin',
  reason?: string,
) {
  return apiFetch<{ admin: ClubAdmin }>(`/system/tenants/${tenantId}/admins`, {
    method: 'POST',
    body: JSON.stringify({ email, level, reason }),
  })
}

export async function removeClubAdmin(tenantId: number, userId: number, reason?: string) {
  return apiFetch(`/system/tenants/${tenantId}/admins/${userId}`, {
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
  }>(`/system/support-sessions?${qs}`)
}

export async function endSupportSession(session: string) {
  return apiFetch<{ ended: string }>(
    `/system/support-sessions/${encodeURIComponent(session)}/end`,
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
  return apiFetch(`/system/tenants/health${s ? `?${s}` : ''}`)
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
  return apiFetch<TenantTrends>(`/system/tenants/${tenantId}/trends?range=${range}`)
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

export interface TenantLimits {
  plan: string
  warn_percent: number
  limits: Record<LimitKind, LimitRow>
}

export async function getTenantLimits(tenantId: number) {
  return apiFetch<TenantLimits>(`/system/tenants/${tenantId}/limits`)
}

/** A number, null for no limit, or "plan" to follow the plan again. */
export async function setTenantLimits(
  tenantId: number,
  values: Partial<Record<LimitKind, number | null | 'plan'>>,
) {
  return apiFetch<TenantLimits>(`/system/tenants/${tenantId}/limits`, {
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
  return apiFetch<TenantEarlyAccess>(`/system/tenants/${tenantId}/early-access`)
}

export async function setTenantEarlyAccess(
  tenantId: number,
  body: { early_access?: boolean; features?: Record<string, boolean | null> },
) {
  return apiFetch<TenantEarlyAccess>(`/system/tenants/${tenantId}/early-access`, {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}

// ── Billing terms (stored and shown only, nothing is charged yet) ────────────

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
  price_chf: string
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
  note: string
}

export interface TenantBilling extends BillingTerms {
  plan: string
  plan_price_chf: string | null
  base_chf: string
  discount_chf: string
  addons_chf: string
  total_chf: string
  due_chf: string
  sponsorship_running: boolean
  sponsorship_days_left: number | null
  sponsorship_ending_soon: boolean
  sponsorship_ended: boolean
  trial_days_left: number | null
}

export async function getTenantBilling(tenantId: number) {
  return apiFetch<TenantBilling>(`/system/tenants/${tenantId}/billing`)
}

export async function setTenantBilling(tenantId: number, values: Partial<BillingTerms>) {
  return apiFetch<TenantBilling>(`/system/tenants/${tenantId}/billing`, {
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
}

export interface PlanChoices {
  plans: PlanChoice[]
  addons: { code: string; name: string; price_month_chf: string | null }[]
}

export async function listPlanChoices() {
  return apiFetch<PlanChoices>('/system/plans')
}

export async function setTenantPlan(id: number, plan: string) {
  return apiFetch<{ tenant: Tenant }>(`/system/tenants/${id}`, {
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
  return apiFetch<DataRequestList>(`/system/data-requests?${q}`)
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
  return apiFetch<DataRequest>(`/system/tenants/${tenantId}/data-requests`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function updateDataRequest(
  id: number,
  body: Partial<Pick<DataRequest, 'subject_name' | 'subject_email' | 'member_id' | 'note'>>,
) {
  return apiFetch<DataRequest>(`/system/data-requests/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

/** Downloads the member's data as a JSON file (asks for the password again). */
export async function downloadDataExport(req: DataRequest) {
  const data = await withStepUp(() =>
    apiFetch<unknown>(`/system/data-requests/${req.id}/export`, { method: 'POST' }),
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
    apiFetch<DataRequest>(`/system/data-requests/${id}/delete-member`, {
      method: 'POST',
      body: JSON.stringify({ confirm }),
    }),
  )
}

export async function closeDataRequest(id: number, status: 'done' | 'rejected', outcome: string) {
  return apiFetch<DataRequest>(`/system/data-requests/${id}/${status}`, {
    method: 'POST',
    body: JSON.stringify({ outcome }),
  })
}
