import { useAuth } from '@/context/AppContext'
import { useModules } from '@/modules/useModules'
import { usePlugins } from './store'
import type { PluginRoute, PluginTab } from './types'

type Gated = { module: string; perm?: string; order?: number }

export function useVisible<T extends Gated>(
  pick: (p: ReturnType<typeof usePlugins>[number]) => T[] | undefined,
) {
  const plugins = usePlugins()
  const modules = useModules()
  const { hasPermission } = useAuth()
  return plugins
    .flatMap((p) => pick(p) ?? [])
    .filter((e) => modules.has(e.module) && (!e.perm || hasPermission(e.perm)))
    .sort((a, b) => (a.order ?? 100) - (b.order ?? 100))
}

/** Screens added by plugins; the route itself checks module and permission. */
export function usePluginRoutes(): PluginRoute[] {
  const plugins = usePlugins()
  const modules = useModules()
  return plugins.flatMap((p) => p.routes ?? []).filter((r) => modules.has(r.module))
}

/** Tabs plugins add to `screen`, already filtered for this club and user. */
export function usePluginTabs(screen: string): PluginTab[] {
  return useVisible((p) => p.tabs).filter((t) => t.screen === screen)
}
