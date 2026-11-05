import { apiFetch } from '@hubra/api-client'

/** A token or an app's sign-in in this club (docs/api-tokens.md, docs/oauth.md). */
export interface ClubApiToken {
  id: number
  /** identity: a member signed in to one of the club's sign-in apps. */
  kind: 'member' | 'club' | 'identity'
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

// ── Sign in with Hubra: the club's own apps (docs/oidc.md) ──────────────────

export interface ClubSignInApp {
  id: number
  clientId: string
  name: string
  description: string
  clientUri: string | null
  redirectUris: string[]
  confidential: boolean
  secretLast4: string | null
  createdByName: string
  createdAt: string | null
  lastUsedAt: string | null
  disabledAt: string | null
  activeGrants: number
}

export interface NewClubSignInApp extends ClubSignInApp {
  /** Shown once. */
  clientSecret?: string
}

export interface ClubSignInAppInput {
  name: string
  description?: string
  clientUri?: string | null
  redirectUris: string[]
  confidential?: boolean
}

export async function listClubSignInApps(): Promise<{
  items: ClubSignInApp[]
  issuer: string
  discoveryUrl: string
  max: number
}> {
  return apiFetch('/app/oauth/apps')
}

export async function createClubSignInApp(body: ClubSignInAppInput): Promise<NewClubSignInApp> {
  return apiFetch('/app/oauth/apps', { method: 'POST', body: JSON.stringify(body) })
}

export async function editClubSignInApp(
  id: number,
  body: Partial<ClubSignInAppInput> & { disabled?: boolean },
): Promise<ClubSignInApp> {
  return apiFetch(`/app/oauth/apps/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
}

export async function newClubSignInAppSecret(id: number): Promise<NewClubSignInApp> {
  return apiFetch(`/app/oauth/apps/${id}/secret`, { method: 'POST' })
}

export async function deleteClubSignInApp(id: number): Promise<void> {
  await apiFetch(`/app/oauth/apps/${id}`, { method: 'DELETE' })
}
