import { apiFetch } from '@hubra/api-client'

/** OAuth apps (docs/oauth.md): outside apps that act for a person with
 * their consent, such as Claude. */
const P = '/platform/oauth/apps'

export interface OAuthApp {
  id: number
  clientId: string
  /** registered: by a platform admin; dynamic: Claude registered itself. */
  kind: 'registered' | 'dynamic'
  name: string
  description: string
  clientUri: string | null
  redirectUris: string[]
  /** Has a secret (else PKCE only). */
  confidential: boolean
  secretLast4: string | null
  resources: ('api' | 'mcp')[]
  scopes: ('read' | 'write')[]
  createdByName: string
  createdAt: string | null
  lastUsedAt: string | null
  disabledAt: string | null
  activeGrants: number
}

export interface OAuthAppList {
  items: OAuthApp[]
  issuer: string
  metadataUrl: string
  mcpResource: string | null
  dynamicAllowed: boolean
}

export type NewOAuthApp = OAuthApp & { clientSecret?: string }

export interface OAuthAppInput {
  name: string
  description?: string
  clientUri?: string | null
  redirectUris: string[]
  resources: ('api' | 'mcp')[]
  scopes: ('read' | 'write')[]
  confidential?: boolean
}

export const listOAuthApps = (): Promise<OAuthAppList> => apiFetch(P)

export const createOAuthApp = (body: OAuthAppInput): Promise<NewOAuthApp> =>
  apiFetch(P, { method: 'POST', body: JSON.stringify(body) })

export const editOAuthApp = (
  id: number,
  body: Partial<OAuthAppInput> & { disabled?: boolean },
): Promise<OAuthApp> => apiFetch(`${P}/${id}`, { method: 'PATCH', body: JSON.stringify(body) })

export const newOAuthAppSecret = (id: number): Promise<NewOAuthApp> =>
  apiFetch(`${P}/${id}/secret`, { method: 'POST' })

export const deleteOAuthApp = (id: number): Promise<void> =>
  apiFetch(`${P}/${id}`, { method: 'DELETE' })
