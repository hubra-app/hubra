import { Link, useLocation } from 'react-router-dom'
import { Button } from '@mantine/core'
import { IconSettings } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { PageHead } from '@/components/ui'
import { EventsTab } from '@/screens/private/operations/EventsTab'
import { PollsTab } from '@/screens/private/operations/PollsTab'
import { PostsTab } from '@/screens/private/operations/PostsTab'
import { useModules } from '@/modules/useModules'
import { useAuth } from '@/context/AppContext'

export function OperationsTabScreen() {
  const { t } = useT()
  const location = useLocation()

  const { has } = useModules()
  const { hasPermission } = useAuth()

  const tabs = [
    { id: 'events', label: t('shell.nav.events') },
    { id: 'polls', label: t('shell.nav.polls') },
    { id: 'posts', label: t('shell.nav.posts') },
  ].filter((tb) => has(tb.id))

  const path = location.pathname.replace('/app/operations', '').replace('/', '')
  const tab = path === '' ? (tabs[0]?.id ?? 'events') : path

  // Anlässe, Umfragen and Beiträge each have their own sidebar entry, so the
  // page only shows the one that was picked.
  const title = tabs.find((tb) => tb.id === tab)?.label ?? t('shell.nav.events')

  return (
    <div>
      <PageHead
        title={title}
        actions={
          // The module's settings (notify members, reminders, event types)
          // live with the other module settings; this opens them directly.
          hasPermission('modules.modules.write') && (
            <Button
              component={Link}
              to={`/app/settings/modules?module=${tab}`}
              variant="default"
              leftSection={<IconSettings size={16} />}
            >
              {t('settings.modules.configure', 'Einstellungen')}
            </Button>
          )
        }
      />
      {tab === 'events' && <EventsTab />}
      {tab === 'polls' && <PollsTab />}
      {tab === 'posts' && <PostsTab />}
    </div>
  )
}
