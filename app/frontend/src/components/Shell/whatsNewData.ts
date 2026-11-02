import { useSyncExternalStore } from 'react'
import { useQuery } from '@tanstack/react-query'
import { latestReleaseKey } from '@hubra/ui'
import { getChangelog } from '@/api/system'
import { qk } from '@/data/keys'
import { subscribeWhatsNew, whatsNewSeen } from './whatsNewStore'

/** The release notes, loaded once per visit and shared with the menu's "new" mark. */
export function useChangelog(enabled = true) {
  return useQuery({
    queryKey: qk.changelog,
    queryFn: getChangelog,
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
