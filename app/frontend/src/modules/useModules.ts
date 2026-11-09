import { useData } from '@/context/AppContext'

/**
 * `has('budgets')` is true while that module is on for the active club;
 * `canUse('budgets')` also needs the person's roles to include it
 * (docs/roles.md). Use `canUse` for the module's own pages, tabs, widgets
 * and search, `has` for the person's own data from it (profile cards).
 */
export function useModules() {
  const { modules, moduleList, modulesLoaded } = useData()
  return {
    has: (code: string) => modules[code] === true,
    canUse: (code: string) =>
      modules[code] === true && moduleList.find((m) => m.code === code)?.access !== false,
    list: moduleList,
    loaded: modulesLoaded,
  }
}
