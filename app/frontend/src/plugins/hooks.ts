import { useAuth } from '@/context/AppContext'
import { useModules } from '@/modules/useModules'
import { usePlugins } from './store'
import type { PluginRoute, PluginTab } from './types'

type Gated = { module: string; perm?: string; order?: number }

/** An entry together with the id of the plugin that registered it. */
export type FromPlugin<T> = T & { plugin: string }

export function useVisible<T extends Gated>(
  pick: (p: ReturnType<typeof usePlugins>[number]) => T[] | undefined,
): FromPlugin<T>[] {
  const plugins = usePlugins()
  const modules = useModules()
  const { hasPermission } = useAuth()
  return plugins
    .flatMap((p) => (pick(p) ?? []).map((e) => ({ ...e, plugin: p.id })))
    .filter((e) => modules.has(e.module) && (!e.perm || hasPermission(e.perm)))
    .sort((a, b) => (a.order ?? 100) - (b.order ?? 100))
}

/** Screens added by plugins; the route itself checks module and permission. */
export function usePluginRoutes(): FromPlugin<PluginRoute>[] {
  const plugins = usePlugins()
  const modules = useModules()
  return plugins
    .flatMap((p) => (p.routes ?? []).map((r) => ({ ...r, plugin: p.id })))
    .filter((r) => modules.has(r.module))
}

/** Tabs plugins add to `screen`, already filtered for this club and user. */
export function usePluginTabs(screen: string): FromPlugin<PluginTab>[] {
  return useVisible((p) => p.tabs).filter((t) => t.screen === screen)
}
