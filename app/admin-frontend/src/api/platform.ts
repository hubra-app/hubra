import { withStepUp } from '@/api/stepUp'
import { apiFetch } from '@hubra/api-client'
import type { ChangelogEntry, RoadmapItem, RoadmapStatus } from '@hubra/ui'

const P = '/manager/platform'

export interface PlatformSetting {
  key: string
  label: string
  description: string
  secret: boolean
  validation: string | null
  /** Empty for secrets: they are never sent back. */
  value: string
  isSet: boolean
  /** "platform" when set here, "env" when it falls back to the deployment config. */
  source: 'platform' | 'env'
}

export async function getPlatformSettings() {
  return (await apiFetch<{ settings: PlatformSetting[] }>(`${P}/settings`)).settings
}

/** `null` resets a key to its env default. */
export async function updatePlatformSettings(values: Record<string, string | null>) {
  return (
    await apiFetch<{ settings: PlatformSetting[] }>(`${P}/settings`, {
      method: 'PATCH',
      body: JSON.stringify(values),
    })
  ).settings
}

export async function sendPlatformTestMail(to: string, via: 'relay' | 'fallback' = 'relay') {
  return apiFetch<{ ok: boolean; to: string }>(`${P}/mail/test`, {
    method: 'POST',
    body: JSON.stringify({ to, via }),
  })
}

export async function sendPlatformTestDiscord(channel: 'log' | 'audit' = 'log') {
  return apiFetch<{ ok: boolean }>(`${P}/discord/test`, {
    method: 'POST',
    body: JSON.stringify({ channel }),
  })
}

// ── Diagnostics (platform.diagnostics; changes need platform.settings) ──────

export interface ServiceStatus {
  ok: boolean
  latency_ms: number
  error?: string
}

export interface BuildReport {
  component: string
  host: string
  commit: string | null
  version: string | null
  seen?: number
}

export interface HealthDetail {
  status: 'ok' | 'degraded' | 'error'
  services: Record<string, ServiceStatus>
  version?: string
  /** Commit the API process was built from; null for a build without one. */
  commit?: string | null
  /** What each backend process reported (API, worker, beat, Discord gateway), per host. */
  processes?: BuildReport[]
  /** The newest upgrade event (started, completed or stuck). */
  last_upgrade?: PlatformEvent | null
  stale?: boolean
  checked_at?: number
}

export interface DiscordServer {
  id: number
  club: string
  clubSlug: string
  server: string
  serverId: string
  status: 'pending' | 'active'
  botOnServer: boolean | null
  lastUsedAt: string | null
  lastError: string | null
  lastErrorAt: string | null
}

export interface DiscordStatus {
  settings: { clientId: boolean; publicKey: boolean; clientSecret: boolean; botToken: boolean }
  configured: boolean
  check: {
    checkedAt?: string
    botOk: boolean | null
    botError?: string
    botUser?: { id: string; username: string }
    guildCount?: number | null
    guildError?: string
    interactionsError?: string
    appIdMismatch?: string
    channelOk?: boolean
    channelName?: string
    channelError?: string
  }
  interactions: { expected: string; actual?: string | null }
  redirectUris: string[]
  linkedRolesUrl?: string
  platformLog: {
    channelId: string
    categories: string[]
    lastOkAt?: string
    lastErrorAt?: string
    lastError?: string
  }
  plugin: { installed: boolean; version: string | null; error: string }
  servers: DiscordServer[]
  linkedAccounts: number
}

export async function getDiscordStatus() {
  return apiFetch<DiscordStatus>(`${P}/discord/status`)
}

export interface DiscordGuild {
  id: string
  name: string
  icon: string | null
}

/** The servers the bot is on, and the one the platform log channel is on. */
export async function getDiscordServers() {
  return apiFetch<{ servers: DiscordGuild[]; currentServerId: string | null }>(
    `${P}/discord/servers`,
  )
}

/** Text channels on a server that the bot can post in. */
export async function getDiscordServerChannels(serverId: string) {
  return apiFetch<{ channels: { id: string; name: string; category: string | null }[] }>(
    `${P}/discord/servers/${encodeURIComponent(serverId)}/channels`,
  )
}

export async function checkDiscordNow() {
  return apiFetch<DiscordStatus>(`${P}/discord/check`, { method: 'POST' })
}

export async function getPlatformHealth() {
  return apiFetch<HealthDetail>(`${P}/health`)
}

export async function getChangelog(lang?: string) {
  return apiFetch<{ version: string; entries: ChangelogEntry[] }>(
    `/version/changelog${lang ? `?lang=${encodeURIComponent(lang)}` : ''}`,
  )
}

export async function getRoadmap() {
  return apiFetch<{ statuses: RoadmapStatus[]; items: RoadmapItem[] }>('/version/roadmap')
}

export interface PermissionEntry {
  method: string
  path: string
  key: string
  display_name: string
  resource: string
  action: string
  blueprint: string
}

export async function getApiPermissions() {
  return apiFetch<PermissionEntry[]>(`${P}/permissions`)
}

export interface MailServerEntry {
  id: string
  type: 'mailbox' | 'alias'
  address: string
  name: string
  disabled: boolean
  targets: string[]
  quotaUsed: number | null
  quotaTotal: number | null
  managed: boolean
  /** The club whose address this is; null for orphans. */
  club: { slug: string; name: string } | null
  mmaId: number | null
  kind: string | null
  linkedId: number | null
  ownerName: string | null
}

export async function getMailServer() {
  return (await apiFetch<{ data: MailServerEntry[] }>(`${P}/mail-server`)).data
}

export async function deleteMailServerOrphan(type: MailServerEntry['type'], id: string) {
  await apiFetch(`${P}/mail-server/${type}/${id}`, { method: 'DELETE' })
}

export async function reconcileMailServer() {
  await apiFetch(`${P}/mail-server/reconcile`, { method: 'POST' })
}

// ── Outbound mail: relay checks, event log, alert choices ──────────────────

export type RelayWhich = 'relay' | 'fallback'

export interface RelayCheck {
  which: RelayWhich
  configured: boolean
  /** null when the relay is not set up. */
  ok: boolean | null
  host?: string
  port?: number
  latency_ms?: number
  steps: { step: string; ok: boolean; ms: number; error?: string }[]
  error?: string
  /** Unix seconds. */
  checked_at: number
  failures?: number
  down?: boolean
  scheduled?: boolean
}

export interface RelaySummary {
  which: RelayWhich
  configured: boolean
  host: string
  port: number | null
  login: boolean
  last_check: RelayCheck | null
}

export interface MailRelayStatus {
  relays: RelaySummary[]
  primary_down: { active: boolean; seconds_left: number }
  stats: { hours: number; sent: number; fallback: number; failed: number }
  check_every_minutes: number
}

export async function getMailRelayStatus() {
  return apiFetch<MailRelayStatus>(`${P}/mail-relay`)
}

export async function checkMailRelay(which?: RelayWhich) {
  return (
    await apiFetch<{ results: RelayCheck[] }>(`${P}/mail-relay/check`, {
      method: 'POST',
      body: JSON.stringify(which ? { which } : {}),
    })
  ).results
}

export async function resumeMainRelay() {
  return apiFetch<{ primary_down: MailRelayStatus['primary_down'] }>(`${P}/mail-relay/use-main`, {
    method: 'POST',
  })
}

export type EventCategory =
  | 'mail'
  | 'relay'
  | 'service'
  | 'backup'
  | 'plugin'
  | 'system'
  | 'alert'
  | 'discord'
export type EventLevel = 'info' | 'warning' | 'error'

export interface PlatformEvent {
  id: number
  time: string
  category: EventCategory
  kind: string
  level: EventLevel
  tenant_id: number | null
  club: string | null
  message: string
  details: Record<string, unknown>
}

export async function getPlatformEvents(params: {
  category?: EventCategory | ''
  level?: EventLevel | 'problems' | ''
  tenant_id?: number
  q?: string
  page: number
  per_page: number
}) {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== '') qs.set(k, String(v))
  })
  return apiFetch<{
    entries: PlatformEvent[]
    total: number
    page: number
    per_page: number
    retention_days: number
  }>(`${P}/events?${qs}`)
}

export type AlertType =
  | 'relay_down'
  | 'fallback_used'
  | 'delivery_failed'
  | 'service_down'
  | 'backup_failed'
  | 'backup_deleted'
  | 'plugin_updates'
  | 'upgrades'
  | 'system'
  | 'support_cases'

export interface OpenProblem {
  id: string
  level: EventLevel
  area: EventCategory | 'performance'
  title: string
  detail: string
  /** Unix seconds. */
  since: number | null
  /** A manage path. */
  link: string
}

export interface Maintenance {
  active: boolean
  message: string
  /** ISO time it ends by itself, or null (until turned off). */
  until: string | null
}

export interface AlertSwitches {
  /** false: no alert goes out by mail or Discord (still logged). */
  enabled: boolean
  /** The platform Discord log is set up with the alerts category. */
  discordReady: boolean
  /** The matrix columns, in order. */
  channels: NotifyChannel[]
  types: Record<AlertType, Record<NotifyChannel, boolean>>
  /** Platform events (audit log categories) per channel; a channel left out is not offered (Discord-only categories have no mail). */
  events: Record<string, Partial<Record<NotifyChannel, boolean>>>
}

export type NotifyChannel = 'mail' | 'discord'

export async function getAlertsOverview() {
  return apiFetch<{
    problems: OpenProblem[]
    recent: PlatformEvent[]
    counts: Partial<Record<EventCategory, { warning: number; error: number }>>
    maintenance: Maintenance
    switches: AlertSwitches
  }>(`${P}/alerts/overview`)
}

export async function getAlertSwitches() {
  return apiFetch<AlertSwitches>(`${P}/alerts/switches`)
}

export async function updateAlertSwitches(change: {
  enabled?: boolean
  types?: Partial<Record<AlertType, Partial<Record<NotifyChannel, boolean>>>>
  events?: Record<string, Partial<Record<NotifyChannel, boolean>>>
}) {
  return apiFetch<AlertSwitches>(`${P}/alerts/switches`, {
    method: 'PUT',
    body: JSON.stringify(change),
  })
}

export async function setMaintenance(body: {
  on: boolean
  message?: string
  minutes?: number | null
}) {
  return apiFetch<Maintenance>(`${P}/maintenance`, {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}

export interface PerfRoute {
  route: string
  method: string
  requests: number
  /** Milliseconds, estimated from duration buckets. */
  p50: number | null
  p95: number | null
  mean: number | null
  dbMean: number | null
  queriesMean: number | null
  slow: number
  status: Partial<Record<'1xx' | '2xx' | '3xx' | '4xx' | '5xx', number>>
  totalMs: number
}

export interface PerfQuery {
  id: string
  /** Normalized: every value is "?". */
  sql: string
  where: string
  count: number
  meanMs: number | null
  maxMs: number
  totalMs: number
}

export interface PerfSummary {
  hours: number
  source: 'redis' | 'memory'
  thresholds: { slow_request_ms: number; slow_query_ms: number; p95_warning_ms: number }
  total: Omit<PerfRoute, 'route' | 'method'>
  lastHour: Pick<PerfRoute, 'requests' | 'p50' | 'p95' | 'slow' | 'status'>
  routes: PerfRoute[]
  routeCount: number
  queries: PerfQuery[]
}

export async function getPerformance(hours: number) {
  return apiFetch<PerfSummary>(`${P}/alerts/performance?hours=${hours}`)
}

export async function getMyAlerts() {
  return apiFetch<{
    alerts: Record<AlertType, boolean>
    email: string
    receives: boolean
    cooldownMinutes: number
  }>(`${P}/alerts/me`)
}

export async function updateMyAlerts(values: Partial<Record<AlertType, boolean>>) {
  return (
    await apiFetch<{ alerts: Record<AlertType, boolean> }>(`${P}/alerts/me`, {
      method: 'PUT',
      body: JSON.stringify(values),
    })
  ).alerts
}

// ── Encryption keys (platform.settings) ─────────────────────────────────────

export interface KeyReport {
  total: number
  current: number
  /** Values (or club keys) still on an old key. */
  old_key: number
  /** Values no configured key opens: a key is missing from FERNET_OLD_KEYS. */
  unreadable: number
  rotated: number
  new_keys: number
  clean: boolean
}

export interface ClubKeys {
  tenant_id: number
  slug: string
  name: string
  /** Newest data key version; null until the club stores its first secret. */
  key_version: number | null
  key_created_at: string | null
  backup_public_key: string | null
  /** The club chose "only our key": new backups don't open with the platform key. */
  backup_club_only: boolean
}

export interface EncryptionStatus {
  master: { fernet_key_set: boolean; old_keys: number }
  values: KeyReport
  clubs: ClubKeys[]
}

export async function getEncryption() {
  return apiFetch<EncryptionStatus>(`${P}/encryption`)
}

/** Without `newKeys`: move everything onto the current keys. With it, new data keys too. */
export async function rotateEncryption(newKeys = false, tenantId?: number) {
  return withStepUp(() =>
    apiFetch<KeyReport>(`${P}/encryption/rotate`, {
      method: 'POST',
      body: JSON.stringify(newKeys ? { new_keys: true, tenant_id: tenantId } : {}),
    }),
  )
}

/** `null` removes the club's own backup key. */
export async function setClubBackupKey(tenantId: number, publicKey: string | null) {
  return withStepUp(() =>
    apiFetch<{ tenant_id: number; backup_public_key: string | null }>(
      `${P}/clubs/${tenantId}/backup-key`,
      { method: 'PUT', body: JSON.stringify({ public_key: publicKey }) },
    ),
  )
}

// ── Planned maintenance windows ─────────────────────────────────────────────

export interface MaintenanceWindow {
  id: number
  starts_at: string
  ends_at: string
  message: string
  /** null: every club. */
  tenant_ids: number[] | null
  clubs: { id: number; name: string | null }[] | null
  notice_hours: number
  status: 'planned' | 'announced' | 'running' | 'done' | 'cancelled'
  created_by: number | null
  created_at: string | null
  cancelled_at: string | null
}

export async function getMaintenanceWindows() {
  return apiFetch<{
    current: MaintenanceWindow[]
    past: MaintenanceWindow[]
    notice_hours: number[]
  }>(`${P}/maintenance/windows`)
}

export async function createMaintenanceWindow(body: {
  starts_at: string
  ends_at: string
  message: string
  tenant_ids: number[] | null
  notice_hours: number
}) {
  return apiFetch<{ window: MaintenanceWindow }>(`${P}/maintenance/windows`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function cancelMaintenanceWindow(id: number) {
  return apiFetch<{ window: MaintenanceWindow }>(`${P}/maintenance/windows/${id}/cancel`, {
    method: 'POST',
  })
}

// ── Background jobs (Diagnose › Hintergrundjobs) ─────────────────────────────

export interface JobCounts {
  sent: number
  done: number
  failed: number
  retried: number
}

export interface JobTaskRow extends JobCounts {
  task: string
  avg_ms: number | null
}

export interface FailedJob {
  id: string
  task_id: string
  task: string
  time: string
  tenant_id: number | null
  club: string | null
  error: string
  traceback: string
  retries: number
  can_retry: boolean
  args: unknown[] | null
  kwargs: Record<string, unknown> | null
  retried_at: string | null
  retried_by: string | null
  retry_task_id: string | null
}

export interface RunningJob {
  id: string
  task: string
  tenant_id: number | null
  club: string | null
  started: string
  seconds: number
}

export interface JobsOverview {
  hours: number
  totals: JobCounts
  tasks: JobTaskRow[]
  series: JobCounts[]
  /** null when the broker cannot be read. */
  queued: number | null
  reserved: number | null
  running: RunningJob[]
  failed: FailedJob[]
  failed_keep_days: number
}

export async function getJobs(hours: number) {
  return apiFetch<JobsOverview>(`${P}/jobs?hours=${hours}`)
}

export async function retryJob(id: string) {
  return apiFetch<{ job: FailedJob }>(`${P}/jobs/failed/${encodeURIComponent(id)}/retry`, {
    method: 'POST',
  })
}

export async function dismissJob(id: string) {
  return apiFetch<{ removed: string }>(`${P}/jobs/failed/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })
}

// ── Early access (Einstellungen › Früher Zugang) ─────────────────────────────

export type FeatureStage = 'off' | 'early' | 'all'

export interface FeatureFlag {
  key: string
  title_de: string
  title_en: string
  description_de: string
  description_en: string
  stage: FeatureStage
  clubs_on: number
  /** Clubs that have it forced on / off for themselves. */
  forced_on: number[]
  forced_off: number[]
}

export interface FeaturesOverview {
  flags: FeatureFlag[]
  early_access: { id: number; name: string; slug: string }[]
  clubs_total: number
}

export async function getFeatures() {
  return apiFetch<FeaturesOverview>(`${P}/features`)
}

export async function setFeatureStage(key: string, stage: FeatureStage) {
  return apiFetch<FeaturesOverview>(`${P}/features/${encodeURIComponent(key)}`, {
    method: 'PUT',
    body: JSON.stringify({ stage }),
  })
}

// ── Errors grouped by route and build (Diagnose › Fehler) ────────────────────

export type ErrorStatus = 'open' | 'resolved'

export interface ErrorGroupRow {
  id: number
  exc_type: string
  route: string
  location: string
  message: string
  count: number
  first_seen: string
  last_seen: string
  /** "1.4.0 (abc1234)": the build it first happened on. */
  first_build: string
  first_commit: string | null
  last_build: string
  /** Occurrences per build label. */
  builds: Record<string, number>
  status: ErrorStatus
  resolved_at: string | null
  reopened_at: string | null
  last_tenant_id: number | null
  /** First seen on the build running now. */
  new_in_current: boolean
}

export interface ErrorGroupDetail extends ErrorGroupRow {
  traceback: string
  /** The upgrade that brought the first build, if the event log has it. */
  release: { kind: string; at: string; message: string } | null
  last_club: { id: number; name: string } | null
}

export interface ErrorList {
  errors: ErrorGroupRow[]
  total: number
  page: number
  per_page: number
  counts: Record<ErrorStatus, number>
  current_build: string
  builds: Record<string, number>
}

export async function getErrors(params: {
  status: ErrorStatus | 'all'
  q?: string
  sort?: 'last_seen' | 'count' | 'first_seen'
  build?: string
  page?: number
  per_page?: number
}) {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') qs.set(k, String(v))
  }
  return apiFetch<ErrorList>(`${P}/errors?${qs}`)
}

export async function getError(id: number) {
  return apiFetch<{ error: ErrorGroupDetail }>(`${P}/errors/${id}`)
}

export async function setErrorStatus(id: number, action: 'resolve' | 'reopen') {
  return apiFetch<{ error: ErrorGroupRow }>(`${P}/errors/${id}/${action}`, { method: 'POST' })
}

// ── Plans and add-ons with list prices (Einstellungen › Tarife) ──────────────

export interface PlanFeature {
  de: string
  en: string
}

/** flat: once per club; member: each member not archived; license: each licence. */
export type PriceUnit = 'flat' | 'member' | 'license'

/** A module a plan includes; price_chf null: at no extra cost. */
export interface PlanModuleInput {
  code: string
  price_chf: string | null
  unit: PriceUnit
}

export interface PlanModule extends PlanModuleInput {
  name_de: string
  name_en: string
  plugin: string | null
  included: boolean
}

export interface Plan {
  key: string
  name_de: string
  name_en: string
  description_de: string
  description_en: string
  price_month_chf: string | null
  price_year_chf: string | null
  features: PlanFeature[]
  modules: PlanModule[]
  limits: { members: number | null; mail_month: number | null; storage_mb: number | null }
  highlighted: boolean
  sort: number
  public: boolean
  hidden: boolean
  clubs: number
}

export interface Addon {
  code: string
  name: string
  description: string
  plugin: string | null
  price_month_chf: string | null
  price_unit: PriceUnit
  public: boolean
  label_de: string
  label_en: string
  note_de: string
  note_en: string
  /** Keys of the plans that include this module. */
  included_in: string[]
}

/** What a plan form sends (limits flattened, like the API takes them). */
export interface PlanInput {
  key?: string
  name_de?: string
  name_en?: string
  description_de?: string
  description_en?: string
  price_month_chf?: string | null
  price_year_chf?: string | null
  features?: PlanFeature[]
  modules?: PlanModuleInput[]
  limit_members?: number | null
  limit_mail_month?: number | null
  limit_storage_mb?: number | null
  public?: boolean
  highlighted?: boolean
  sort?: number
  hidden?: boolean
}

export async function getPlans() {
  return apiFetch<{ plans: Plan[]; addons: Addon[] }>(`${P}/plans`)
}

export async function createPlan(body: PlanInput) {
  return apiFetch<Plan>(`${P}/plans`, { method: 'POST', body: JSON.stringify(body) })
}

export async function updatePlan(key: string, body: PlanInput) {
  return apiFetch<Plan>(`${P}/plans/${encodeURIComponent(key)}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

export async function deletePlan(key: string) {
  return apiFetch<void>(`${P}/plans/${encodeURIComponent(key)}`, { method: 'DELETE' })
}

export async function setAddon(
  code: string,
  body: Partial<
    Pick<
      Addon,
      'price_month_chf' | 'price_unit' | 'public' | 'label_de' | 'label_en' | 'note_de' | 'note_en'
    >
  >,
) {
  return apiFetch<Addon>(`${P}/addons/${encodeURIComponent(code)}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}
