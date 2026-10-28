import { useLocation, useNavigate } from 'react-router-dom'
import { useT } from '@/locales/i18n'
import { PageHead, Tabs } from '@/components/ui'
import { EventsTab } from '@/screens/private/operations/EventsTab'
import { PollsTab } from '@/screens/private/operations/PollsTab'
import { PostsTab } from '@/screens/private/operations/PostsTab'
import { useModules } from '@/modules/useModules'

export function OperationsTabScreen() {
  const { t } = useT()
  const location = useLocation()
  const navigate = useNavigate()

  const { has } = useModules()

  const tabs = [
    { id: 'events', label: t('shell.nav.events') },
    { id: 'polls', label: t('shell.nav.polls') },
    { id: 'posts', label: t('shell.nav.posts') },
  ].filter((tb) => has(tb.id))

  const path = location.pathname.replace('/app/operations', '').replace('/', '')
  const tab = path === '' ? (tabs[0]?.id ?? 'events') : path

  return (
    <div>
      <PageHead title={t('shell.nav.operations', 'Operations')} />
      <Tabs
        tabs={tabs}
        activeTab={tab}
        onTabChange={(id) => navigate(`/app/operations/${id}`)}
      />
      {tab === 'events' && <EventsTab />}
      {tab === 'polls' && <PollsTab />}
      {tab === 'posts' && <PostsTab />}
    </div>
  )
}
