import { withStepUp } from '@/api/stepUp'
import { apiFetch } from '@hubra/api-client'

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
