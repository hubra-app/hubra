import { apiFetch } from '@hubra/api-client'

export interface ModuleNavItem {
  path: string
  labelKey: string
  icon: string
  section: 'workspace' | 'operations' | 'system' | 'me' | string
  order: number
  perms: string[]
  group: string | null
}

export interface ModuleSettingField {
  key: string
  type: 'str' | 'int' | 'bool' | 'float' | 'secret' | 'url' | 'email' | 'choice'
  default: string | number | boolean | null
  label: string
  description: string
  required: boolean
  choices: string[]
}

export interface ModuleInfo {
  code: string
  name: string
  description: string
  dependsOn: string[]
  required: boolean
  defaultEnabled: boolean
  /** Effectively on: switched on, allowed, and every dependency on. */
  enabled: boolean
  switchedOn: boolean
  /** False when the platform manager blocked the module for this club. */
  allowed: boolean
  missingDependencies: string[]
  nav: ModuleNavItem[]
  settings: ModuleSettingField[]
  config: Record<string, string | number | boolean | null>
  configured: boolean
}

export async function getModules(): Promise<ModuleInfo[]> {
  return apiFetch<ModuleInfo[]>('/modules/')
}

export async function setModuleEnabled(code: string, enabled: boolean): Promise<ModuleInfo> {
  return apiFetch<ModuleInfo>(`/modules/${code}`, {
    method: 'PUT',
    body: JSON.stringify({ enabled }),
  })
}

export async function saveModuleSettings(
  code: string,
  config: Record<string, unknown>,
): Promise<ModuleInfo> {
  return apiFetch<ModuleInfo>(`/modules/${code}/settings`, {
    method: 'PUT',
    body: JSON.stringify({ config }),
  })
}

/** Discord module: post a test message to the configured webhook. */
export const sendDiscordTest = () => apiFetch<{ ok: boolean }>('/discord/test', { method: 'POST' })
