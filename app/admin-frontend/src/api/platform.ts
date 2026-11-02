import { withStepUp } from '@/api/stepUp'
import { apiFetch } from '@hubra/api-client'

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

export async function sendPlatformTestDiscord() {
  return apiFetch<{ ok: boolean }>(`${P}/discord/test`, { method: 'POST' })
}

// ── Diagnostics (platform.diagnostics; changes need platform.settings) ──────

export interface ServiceStatus {
  ok: boolean
  latency_ms: number
  error?: string
}

export interface HealthDetail {
  status: 'ok' | 'degraded' | 'error'
  services: Record<string, ServiceStatus>
  version?: string
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

export interface ChangelogEntry {
  version: string
  date: string | null
  sections: Record<string, string[]>
}

export async function getChangelog() {
  return apiFetch<{ entries: ChangelogEntry[] }>('/version/changelog')
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
  | 'plugin_updates'
  | 'system'

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

export async function getAlertsOverview() {
  return apiFetch<{
    problems: OpenProblem[]
    recent: PlatformEvent[]
    counts: Partial<Record<EventCategory, { warning: number; error: number }>>
  }>(`${P}/alerts/overview`)
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
