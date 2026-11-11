import { useMemo, useSyncExternalStore } from 'react'
import { useQuery } from '@tanstack/react-query'
import { latestReleaseKey, type Lang } from '@hubra/ui'
import { useT } from '@/locales/i18n'
import { getChangelog, type ChangelogReader } from '@/api/system'
import { useAuth } from '@/context/AppContext'
import { useModules } from '@/modules/useModules'
import { qk } from '@/data/keys'
import { subscribeWhatsNew, whatsNewSeen } from './whatsNewStore'

/** German or English, from the club app's language. */
export function useReleaseLang(): Lang {
  const { i18n } = useT()
  return i18n.language?.startsWith('en') ? 'en' : 'de'
}

/** This reader in this club: the modules they can use and whether they are
 *  an admin, so What's new leaves out changes to other modules. */
function useChangelogReader(): ChangelogReader | null {
  const { isAdmin } = useAuth()
  const { list, loaded, canUse } = useModules()
  const codes = loaded ? list.filter((m) => canUse(m.code)).map((m) => m.code).sort().join(',') : null
  return useMemo(
    () => (codes === null ? null : { modules: codes ? codes.split(',') : [], admin: isAdmin }),
    [codes, isAdmin],
  )
}

/** The release notes, loaded once per visit and shared with the menu's "new" mark. */
export function useChangelog(enabled = true) {
  const lang = useReleaseLang()
  const reader = useChangelogReader()
  const readerKey = reader ? `${reader.admin ? 'a' : 'm'}:${reader.modules.join(',')}` : undefined
  return useQuery({
    queryKey: qk.changelog(lang, readerKey),
    queryFn: () => getChangelog(lang, reader ?? undefined),
    // Wait for the club's modules, so the notes are filtered once.
    enabled: enabled && reader !== null,
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
