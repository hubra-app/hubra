import { useSyncExternalStore } from 'react'
import i18n from '@/locales/i18n'
import type { PluginDefinition } from './types'

/** The plugins whose frontend has loaded, by id. */
let plugins: PluginDefinition[] = []
const listeners = new Set<() => void>()

export function registerPlugin(def: PluginDefinition): void {
  for (const [lng, bundle] of Object.entries(def.translations ?? {})) {
    // Translations edited in the app win over the plugin's own.
    i18n.addResourceBundle(lng, 'translation', bundle, true, false)
  }
  plugins = [...plugins.filter((p) => p.id !== def.id), def]
  listeners.forEach((l) => l())
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function usePlugins(): PluginDefinition[] {
  return useSyncExternalStore(subscribe, () => plugins)
}

export function pluginIcon(name: string) {
  for (const p of plugins) {
    const icon = p.icons?.[name]
    if (icon) return icon
  }
  return undefined
}
