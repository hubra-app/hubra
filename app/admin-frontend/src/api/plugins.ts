import { apiFetch, apiFetchRaw } from '@hubra/api-client'

const P = '/manager/plugins'

export interface PluginTrust {
  /** official, community, unsigned, invalid or bundled */
  status: string
  signer: string
  key_id: string
  detail: string
}

export interface PluginVersion {
  version: string
  hubra: string
  changes: string
  /** Why the publisher withdrew it; empty when it is offered. */
  yanked: string
  date: string
  compatible: boolean
}

export interface MarketplacePlugin {
  id: string
  name: string
  version: string
  description: string
  author: string
  homepage?: string
  license?: string
  tags: string[]
  modules: string[]
  requires: string[]
  bundled: boolean
  trust: PluginTrust
  loaded: boolean
  error: string
  installed: boolean
  installedVersion: string | null
  compatible: boolean
  incompatibleReason: string
  official: boolean
  /** Offered by the official repository. */
  officialSigned?: boolean
  source: string
  repository: string
  repositoryId: number | null
  repoVersion?: string
  latestVersion?: string
  update: boolean
  changes: string
  versions: PluginVersion[]
  /** The installed version was withdrawn, and why. */
  withdrawn: string
  /** Updates are held at this version. */
  held: string
  /** The version a rollback goes back to. */
  previous: string | null
  /** Installed through HUBRA_PLUGINS_AUTOINSTALL, not from here. */
  autoinstalled: boolean
}

export type UpdateMode = 'notify' | 'official' | 'off'

export interface Marketplace {
  plugins: MarketplacePlugin[]
  errors: string[]
  generation: number
  updateMode: UpdateMode
}

/** What an archive would install; confirm or discard it. */
export interface StagedPlugin {
  token: string
  id: string
  name: string
  version: string
  description: string
  author: string
  trust: PluginTrust
  source: string
  repositoryId: number | null
  installedVersion: string | null
  migrations: boolean
  frontend: boolean
  installable: boolean
  needsConfirmation: boolean
}

export interface PluginChange {
  id: string
  version: string
  previous?: string
  generation: number
}

export interface PluginRepository {
  id: number
  name: string
  url: string
  keyId: string
  official: boolean
  enabled: boolean
  addedBy: string | null
  fetchedAt: string | null
  error: string | null
}

export interface TrustedKey {
  id: number | null
  name: string
  keyId: string
  official: boolean
  addedBy?: string
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  body: body === undefined ? undefined : JSON.stringify(body),
})

export const getMarketplace = (fetch = true) =>
  apiFetch<Marketplace>(`${P}/${fetch ? '' : '?fetch=0'}`)

export const getPluginStatus = () =>
  apiFetch<{ generation: number; loaded: Record<string, string>; errors: Record<string, string> }>(
    `${P}/status`,
  )

export async function uploadPlugin(file: File): Promise<StagedPlugin> {
  const form = new FormData()
  form.append('file', file)
  const res = await apiFetchRaw(`${P}/upload`, { method: 'POST', body: form })
  return res.json()
}

export const confirmStaged = (
  token: string,
  acceptUnsigned: boolean,
  repositoryId: number | null,
) =>
  apiFetch<PluginChange>(
    `${P}/stage/${token}/confirm`,
    json('POST', { acceptUnsigned, repositoryId }),
  )

export const discardStaged = (token: string) =>
  apiFetch<void>(`${P}/stage/${token}`, json('DELETE'))

export const installPlugin = (
  id: string,
  body: { version?: string; repositoryId?: number | null },
) =>
  apiFetch<{ installed?: PluginChange; staged?: StagedPlugin }>(
    `${P}/${id}/install`,
    json('POST', body),
  )

export const rollbackPlugin = (id: string) =>
  apiFetch<PluginChange>(`${P}/${id}/rollback`, json('POST'))

export const holdPlugin = (id: string, version: string | null) =>
  apiFetch<{ held: string }>(`${P}/${id}/hold`, json('PUT', { version }))

export const uninstallPlugin = (id: string, deleteData: boolean) =>
  apiFetch<PluginChange>(`${P}/${id}${deleteData ? '?deleteData=1' : ''}`, json('DELETE'))

export const setUpdateMode = (mode: UpdateMode) => apiFetch(`${P}/updates`, json('PUT', { mode }))

export const checkUpdates = () => apiFetch<unknown>(`${P}/updates/check`, json('POST'))

export const listRepositories = () => apiFetch<PluginRepository[]>(`${P}/repositories`)

export const previewRepository = (url: string) =>
  apiFetch<{ name: string; description?: string; keyId: string; plugins: number; url: string }>(
    `${P}/repositories/preview`,
    json('POST', { url }),
  )

export const addRepository = (url: string, keyId: string) =>
  apiFetch<PluginRepository>(`${P}/repositories`, json('POST', { url, keyId }))

export const setRepositoryEnabled = (id: number, enabled: boolean) =>
  apiFetch<PluginRepository>(`${P}/repositories/${id}`, json('PUT', { enabled }))

export const deleteRepository = (id: number) =>
  apiFetch<void>(`${P}/repositories/${id}`, json('DELETE'))

export const listTrustedKeys = () => apiFetch<TrustedKey[]>(`${P}/keys`)

export const addTrustedKey = (name: string, publicKey: string) =>
  apiFetch<TrustedKey>(`${P}/keys`, json('POST', { name, publicKey }))

export const deleteTrustedKey = (id: number) => apiFetch<void>(`${P}/keys/${id}`, json('DELETE'))
