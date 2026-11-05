import { apiFetch } from '@hubra/api-client'

/** A token or an app's sign-in in this club (docs/api-tokens.md, docs/oauth.md). */
export interface ClubApiToken {
  id: number
  kind: 'member' | 'club'
  name: string
  prefix: string
  /** Set when an outside app (OAuth) holds this sign-in. */
  appId: number | null
  resource: string | null
  createdByName: string
  createdAt: string | null
  expiresAt: string | null
  lastUsedAt: string | null
  useCount: number
  revokedAt: string | null
  revokedReason: string | null
  active: boolean
}

export interface ApiAccessSettings {
  membersAllowed: boolean
  aiAllowed: boolean
}

export async function listClubApiTokens(): Promise<{ items: ClubApiToken[]; membersAllowed: boolean }> {
  return apiFetch('/app/api-tokens/')
}

export async function getApiAccessSettings(): Promise<ApiAccessSettings & { isAdmin: boolean }> {
  return apiFetch('/app/api-tokens/scopes')
}

export async function saveApiAccessSettings(changes: Partial<ApiAccessSettings>): Promise<ApiAccessSettings> {
  return apiFetch('/app/api-tokens/settings', { method: 'PUT', body: JSON.stringify(changes) })
}

export async function endClubApiToken(id: number): Promise<void> {
  await apiFetch(`/app/api-tokens/${id}`, { method: 'DELETE' })
}
