import { apiFetch } from '@hubra/api-client'

export interface ModuleNavItem {
  path: string
  labelKey: string
  icon: string
  section: 'workspace' | 'operations' | 'system' | 'me' | string
  order: number
  perms: string[]
  group: string | null
  /** Path of the entry whose screen shows this one as a tab. */
  parent?: string | null
}

export interface ModuleSettingField {
  key: string
  type: 'str' | 'int' | 'bool' | 'float' | 'secret' | 'url' | 'email' | 'choice'
  default: string | number | boolean | null
  label: string
  description: string
  required: boolean
  choices: string[]
  /** Localized names of the choices, set by localizeModule */
  choiceLabels?: Record<string, string>
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
  /** False when the module is priced per licence and the signed-in member
   *  holds none: hidden in their navigation, its API answers 403. */
  licensed?: boolean
  /** False when the member's roles don't include the module (docs/roles.md):
   *  hidden in their navigation, its pages say "Kein Zugriff". Their own
   *  data from it (invoices, claims, items) stays on their profile. */
  access?: boolean
  /** The permission that opens the module, null when everyone with the
   *  right keys uses it. */
  accessKey?: string | null
  nav: ModuleNavItem[]
  settings: ModuleSettingField[]
  config: Record<string, string | number | boolean | null>
  configured: boolean
  /** Set when the module comes from a plugin. */
  plugin?: ModulePlugin
}

export interface ModulePlugin {
  id: string
  name: string
  version: string
  author: string
  /** official, community, unsigned, invalid or bundled */
  trust: string
  /** Cache tag of the plugin's built frontend; null when it has none. */
  frontend: string | null
}

export async function getModules(): Promise<ModuleInfo[]> {
  return apiFetch<ModuleInfo[]>('/app/modules/')
}

export async function setModuleEnabled(code: string, enabled: boolean): Promise<ModuleInfo> {
  return apiFetch<ModuleInfo>(`/app/modules/${code}`, {
    method: 'PUT',
    body: JSON.stringify({ enabled }),
  })
}

export async function saveModuleSettings(
  code: string,
  config: Record<string, unknown>,
): Promise<ModuleInfo> {
  return apiFetch<ModuleInfo>(`/app/modules/${code}/settings`, {
    method: 'PUT',
    body: JSON.stringify({ config }),
  })
}
