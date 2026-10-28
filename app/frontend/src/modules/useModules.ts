import { useData } from '@/context/AppContext'

/** `has('budgets')` is true while that module is on for the active club. */
export function useModules() {
  const { modules, moduleList, modulesLoaded } = useData()
  return {
    has: (code: string) => modules[code] === true,
    list: moduleList,
    loaded: modulesLoaded,
  }
}
