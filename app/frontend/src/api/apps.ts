import { apiFetch } from '@hubra/api-client'

export interface AppScope {
  key: string
  label: string
  description: string
}

export interface AppProviderInfo {
  code: string
  name: string
  description: string
  icon: string
  scopes: AppScope[]
  module: string
  /** Why it can't be connected right now (platform not set up), or null. */
  unavailable: string | null
}

export interface AppEvent {
  action: string
  ok: boolean
  detail: string
  at: string | null
}

export interface Connection {
  id: number
  provider: string
  providerName: string
  externalId: string
  label: string
  status: 'pending' | 'active' | 'revoked'
  scopes: string[]
  config: Record<string, unknown>
  hasSecret: boolean
  createdBy: string
  createdAt: string | null
  confirmedAt: string | null
  lastUsedAt: string | null
  lastError: string | null
  lastErrorAt: string | null
  events?: AppEvent[]
}

export async function listApps(): Promise<{ providers: AppProviderInfo[]; connections: Connection[] }> {
  return apiFetch('/apps/')
}

/** Where to send the browser to sign in on the outside service. */
export async function startConnect(provider: string, scopes: string[]): Promise<{ url: string }> {
  return apiFetch(`/apps/${provider}/connect`, { method: 'POST', body: JSON.stringify({ scopes }) })
}

export async function getConnection(id: number): Promise<Connection> {
  return apiFetch(`/apps/connections/${id}`)
}

export async function confirmConnection(id: number): Promise<Connection> {
  return apiFetch(`/apps/connections/${id}/confirm`, { method: 'POST' })
}

export async function updateConnection(
  id: number,
  changes: { label?: string; scopes?: string[]; config?: Record<string, unknown> },
): Promise<Connection> {
  return apiFetch(`/apps/connections/${id}`, { method: 'PATCH', body: JSON.stringify(changes) })
}

export async function testConnection(id: number): Promise<{ ok: boolean; message: string }> {
  return apiFetch(`/apps/connections/${id}/test`, { method: 'POST' })
}

export async function disconnect(id: number): Promise<void> {
  await apiFetch(`/apps/connections/${id}`, { method: 'DELETE' })
}
