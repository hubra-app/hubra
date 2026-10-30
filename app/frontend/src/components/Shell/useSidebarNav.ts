import { useLocation } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useT } from '@/locales/i18n'
import { useAuth, useData } from '@/context/AppContext'
import { usePlugins } from '@/plugins/store'
import { useNavCounts } from '@/data/lists'
import { qk } from '@/data/keys'
import { getNavPrefs, saveNavPrefs } from '@/api/auth'
import { buildNav, getParentPath, MORE_PATH, navPaths, type NavPrefs } from './nav'

/** The person's pinned and hidden sidebar entries, saved on their account. */
export function useNavPrefs() {
  const queryClient = useQueryClient()
  const { data } = useQuery({
    queryKey: qk.account.navPrefs,
    queryFn: getNavPrefs,
    staleTime: Infinity,
  })
  const save = useMutation({
    mutationFn: saveNavPrefs,
    // The sidebar follows at once; the server's answer replaces it.
    onMutate: (prefs: NavPrefs) => queryClient.setQueryData(qk.account.navPrefs, prefs),
    onSettled: (prefs) => {
      if (prefs) queryClient.setQueryData(qk.account.navPrefs, prefs)
      else queryClient.invalidateQueries({ queryKey: qk.account.navPrefs })
    },
  })
  return { prefs: data ?? { pinned: [], hidden: [] }, save: save.mutate }
}

/**
 * The sidebar as this person sees it, the pages behind "Weitere", and which
 * entry the current page belongs to.
 */
export function useSidebarNav() {
  const { t } = useT()
  const location = useLocation()
  const { hasPermission } = useAuth()
  const { moduleList } = useData()
  const counts = useNavCounts()
  usePlugins() // plugin icons arrive after the first render
  const { prefs } = useNavPrefs()
  const { nav, more, customizable } = buildNav(counts, t, moduleList, hasPermission, prefs)
  const morePaths = more.map((item) => item.path)
  const parent = getParentPath(location.pathname, [...navPaths(nav), ...morePaths])
  const currentMore = morePaths.includes(parent) ? parent : null
  return {
    nav,
    more,
    customizable,
    activePath: currentMore ? MORE_PATH : parent,
    currentMore,
  }
}
