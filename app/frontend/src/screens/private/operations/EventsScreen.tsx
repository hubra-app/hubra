import type { ReactNode } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Button } from '@mantine/core'
import { IconSettings } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { PageHead, Tabs } from '@/components/ui'
import { useAuth } from '@/context/AppContext'
import { PluginBoundary, usePluginTabs } from '@/plugins'
import { EventsTab } from './EventsTab'
import { AttendanceScreen } from './AttendanceScreen'
import { TrialsScreen } from './TrialsScreen'
import { EventDetailScreen } from './EventDetailScreen'
import { useEventPerms } from './eventPerms'

const BASE = '/app/operations/events'
const tabPath = (id: string) => (id === 'list' ? BASE : `${BASE}/${id}`)

/**
 * Anlässe: the club's events, and what belongs with them as tabs. Vor Ort
 * (members say on which days they are in a room) comes from the Booking
 * plugin as a tab on this screen (`screen: 'events'`); attendance and trial
 * trainings are for the organisers. /app/operations/events/<id> with a
 * number is one event's page.
 */
export function EventsScreen() {
  const { t } = useT()
  const location = useLocation()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()
  const perms = useEventPerms()
  const pluginTabs = usePluginTabs('events')

  // The path may start with the club's slug: /<club>/app/operations/events/<tab>.
  const part = (location.pathname.split(BASE)[1] ?? '').replace(/^\//, '').split('/')[0]
  if (/^\d+$/.test(part)) return <EventDetailScreen id={part} />

  const tabs: { id: string; label: string; render: () => ReactNode }[] = [
    { id: 'list', label: t('shell.nav.events', 'Anlässe'), render: () => <EventsTab /> },
    ...pluginTabs.map((pt) => ({
      id: pt.id,
      label: t(pt.label),
      render: () => (
        <PluginBoundary key={pt.id} plugin={pt.plugin} notice>
          <pt.component />
        </PluginBoundary>
      ),
    })),
    ...(perms.seesAttendance
      ? [
          {
            id: 'attendance',
            label: t('events.attendance.overview', 'Anwesenheit'),
            render: () => <AttendanceScreen />,
          },
        ]
      : []),
    ...(perms.seesTrials
      ? [
          {
            id: 'trials',
            label: t('events.trials.title', 'Schnuppertrainings'),
            render: () => <TrialsScreen />,
          },
        ]
      : []),
  ]
  // A tab this person can't open, or one whose plugin hasn't loaded yet (it
  // shows once it has): the list.
  const active = tabs.find((tb) => tb.id === (part || 'list')) ?? tabs[0]

  return (
    <div>
      <PageHead
        title={t('shell.nav.events', 'Anlässe')}
        actions={
          // The module's settings (notify members, reminders, event types)
          // live with the other module settings; this opens them directly.
          hasPermission('modules.modules.write') && (
            <Button
              component={Link}
              to="/app/settings/modules?module=events"
              variant="default"
              leftSection={<IconSettings size={16} />}
            >
              {t('settings.modules.configure', 'Einstellungen')}
            </Button>
          )
        }
      />
      {tabs.length > 1 && (
        <Tabs
          tabs={tabs.map((tb) => ({ id: tb.id, label: tb.label }))}
          activeTab={active.id}
          onTabChange={(id) => navigate(tabPath(id))}
          label={t('shell.nav.events', 'Anlässe')}
        />
      )}
      {active.render()}
    </div>
  )
}
