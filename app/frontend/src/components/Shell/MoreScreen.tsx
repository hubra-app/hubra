import { Navigate } from 'react-router-dom'
import { IconDots } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { PageHead, Tabs } from '@/components/ui'
import { EmptyState } from '@/components/feedback'
import { useNav } from '@/context/AppContext'
import { useSidebarNav } from './useSidebarNav'

/** "Weitere" opens its first page; the tabs above each page switch between them. */
export function MoreScreen() {
  const { t } = useT()
  const { more } = useSidebarNav()
  if (more.length > 0) return <Navigate to={more[0].path} replace />
  return (
    <div>
      <PageHead title={t('shell.nav.more')} />
      <EmptyState
        icon={<IconDots size={26} stroke={1.6} />}
        title={t('shell.more.emptyTitle')}
        description={t('shell.more.emptyDesc')}
      />
    </div>
  )
}

/** The tabs of the "Weitere" pages, shown above whichever of them is open. */
export function MoreTabs() {
  const { go } = useNav()
  const { more, currentMore } = useSidebarNav()
  if (!currentMore) return null
  return (
    <Tabs
      tabs={more.map((item) => ({ id: item.path, label: item.label }))}
      activeTab={currentMore}
      onTabChange={go}
    />
  )
}
