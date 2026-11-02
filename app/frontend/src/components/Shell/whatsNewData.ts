import { useSyncExternalStore } from 'react'
import { useQuery } from '@tanstack/react-query'
import { latestReleaseKey, type Lang } from '@hubra/ui'
import { useT } from '@/locales/i18n'
import { getChangelog } from '@/api/system'
import { qk } from '@/data/keys'
import { subscribeWhatsNew, whatsNewSeen } from './whatsNewStore'

/** German or English, from the club app's language. */
export function useReleaseLang(): Lang {
  const { i18n } = useT()
  return i18n.language?.startsWith('en') ? 'en' : 'de'
}

/** The release notes, loaded once per visit and shared with the menu's "new" mark. */
export function useChangelog(enabled = true) {
  const lang = useReleaseLang()
  return useQuery({
    queryKey: qk.changelog(lang),
    queryFn: () => getChangelog(lang),
    enabled,
    staleTime: 30 * 60 * 1000,
  })
}

/** True while the newest release notes have not been opened in this browser. */
export function useWhatsNewUnseen() {
  const { data } = useChangelog()
  const seen = useSyncExternalStore(subscribeWhatsNew, whatsNewSeen)
  const key = data ? latestReleaseKey(data.entries) : null
  return !!key && key !== seen
}
