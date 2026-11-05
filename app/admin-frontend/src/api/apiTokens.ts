import { withStepUp } from '@/api/stepUp'
import { apiFetch } from '@hubra/api-client'

/** Platform API tokens (docs/api-tokens.md): read-only, for scripts and
 * the Claude connector (docs/mcp.md). */
const P = '/platform/api-tokens'

export interface ApiToken {
  id: number
  kind: 'member' | 'club' | 'platform'
  name: string
  /** hbr_plat_<id>_…<last4>: never the secret. */
  prefix: string
  scopes: string[]
  allowedIps: string[]
  createdByName: string
  createdAt: string | null
  expiresAt: string | null
  lastUsedAt: string | null
  lastUsedIp: string | null
  useCount: number
  revokedAt: string | null
  revokedByName: string | null
  revokedReason: string | null
  active: boolean
  /** Set when an outside app holds this sign-in (OAuth, docs/oauth.md). */
  appId?: number | null
  /** Only on the all-tokens list. */
  club?: { slug: string; name: string } | null
}

/** A new or rolled token: the secret, once. */
export interface NewApiToken extends ApiToken {
  token: string
  previous?: ApiToken
}

export interface MyPlatformTokens {
  items: ApiToken[]
  grantable: string[]
  maxDays: number
  mcpUrl: string
}

export async function getMyPlatformTokens() {
  return apiFetch<MyPlatformTokens>(`${P}/mine`)
}

export async function makePlatformToken(body: {
  name: string
  scopes: string[]
  days: number
  allowedIps?: string[]
}) {
  return withStepUp(() =>
    apiFetch<NewApiToken>(`${P}/mine`, { method: 'POST', body: JSON.stringify(body) }),
  )
}

export async function editPlatformToken(id: number, body: { name?: string; scopes?: string[] }) {
  return withStepUp(() =>
    apiFetch<ApiToken>(`${P}/mine/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  )
}

export async function rollPlatformToken(id: number, body: { graceHours: number; days?: number }) {
  return withStepUp(() =>
    apiFetch<NewApiToken>(`${P}/mine/${id}/roll`, { method: 'POST', body: JSON.stringify(body) }),
  )
}

export async function revokeMyPlatformToken(id: number) {
  return apiFetch<unknown>(`${P}/mine/${id}`, { method: 'DELETE' })
}

export async function getAllApiTokens() {
  return (await apiFetch<{ items: (ApiToken & { tenantId: number | null })[] }>(`${P}/`)).items
}

export async function revokeAnyApiToken(id: number) {
  return apiFetch<unknown>(`${P}/${id}`, { method: 'DELETE' })
}
