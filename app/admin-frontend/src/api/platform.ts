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

export async function sendPlatformTestMail(to: string) {
  return apiFetch<{ ok: boolean; to: string }>(`${P}/mail/test`, {
    method: 'POST',
    body: JSON.stringify({ to }),
  })
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
