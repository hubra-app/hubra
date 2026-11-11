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
import { useContentGroups } from './contentGroups'
import { EventDetail } from './EventDetail'

type Part = { id: string; label: string; allowed: boolean; render: () => ReactNode }

const eventsPath = (id: string) => `/app/operations/events${id === 'list' ? '' : '/' + id}`

/**
 * Anlässe in page tabs: the events themselves, the tabs plugins bring (such
 * as Booking's Vor Ort, who is in which room on which day), the attendance
 * overview and the trial bookings. Each tab keeps its own address
 * (/app/operations/events/<tab>), so old links to the attendance and the
 * trials still open the same page.
 */
export function EventsPage() {
  const { t } = useT()
  const location = useLocation()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()
  // Group leaders take the roll of their own group's events.
  const rollScope = useContentGroups('events.events.add_attendee')
  const pluginTabs = usePluginTabs('events')

  const seesAttendance = rollScope.canAny

  const parts: Part[] = [
    {
      id: 'list',
      label: t('shell.nav.events', 'Anlässe'),
      allowed: true,
      render: () => <EventsTab />,
    },
    ...pluginTabs.map((pt) => ({
      id: pt.id,
      label: t(pt.label),
      allowed: true,
      render: () => (
        <PluginBoundary key={pt.id} plugin={pt.plugin} notice>
          <pt.component />
        </PluginBoundary>
      ),
    })),
    {
      id: 'attendance',
      label: t('events.attendance.overview', 'Anwesenheit'),
      allowed: seesAttendance,
      render: () => <AttendanceScreen />,
    },
    {
      id: 'trials',
      label: t('events.trials.button', 'Schnuppern'),
      allowed: hasPermission('events.trials.read'),
      render: () => <TrialsScreen />,
    },
  ].filter((p) => p.allowed)

  // The path may start with the club's slug: /<club>/app/operations/events/<tab>.
  const rest = (location.pathname.split('/app/operations/events')[1] ?? '').replace(/^\//, '')
  const active = parts.find((p) => p.id === rest)?.id ?? 'list'
  const part = parts.find((p) => p.id === active)

  // /app/operations/events/<id>: one event on its own page.
  if (/^\d+$/.test(rest)) return <EventDetail id={rest} />

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
      {parts.length > 1 && (
        <Tabs
          tabs={parts.map((p) => ({ id: p.id, label: p.label }))}
          activeTab={active}
          onTabChange={(id) => navigate(eventsPath(id) + (id === active ? location.search : ''))}
        />
      )}
      {part?.render()}
    </div>
  )
}
