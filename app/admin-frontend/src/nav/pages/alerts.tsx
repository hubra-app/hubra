import { IconBell } from '@tabler/icons-react'
import { tr } from '@/lang'
import { lazyNamed } from '@/lazyNamed'
import { definePage, icon } from '../registry'

const EventsPanel = lazyNamed(() => import('@/screens/platform/Alerts'), 'EventsPanel')
const OverviewPanel = lazyNamed(() => import('@/screens/platform/Alerts'), 'OverviewPanel')
const RulesPanel = lazyNamed(() => import('@/screens/platform/Alerts'), 'RulesPanel')
const MyAlertsCard = lazyNamed(() => import('@/screens/platform/MailMonitor'), 'MyAlertsCard')
const SettingsSection = lazyNamed(() => import('@/screens/platform/SettingsSection'), 'SettingsSection')

export default definePage('operations', 10, () => ({
  id: 'alerts',
  label: tr('Warnungen', 'Alerts'),
  icon: icon(IconBell),
  desc: tr(
    'Was gerade nicht stimmt, alles, was passiert ist, und wer welche Warnung bekommt.',
    'What is wrong right now, everything that happened, and who gets which alert.',
  ),
  tabs: [
    {
      id: 'overview',
      path: '/app/platform/alerts',
      label: tr('Übersicht', 'Overview'),
      perm: 'platform.diagnostics',
      render: () => <OverviewPanel />,
    },
    {
      id: 'events',
      path: '/app/platform/alerts/events',
      label: tr('Ereignisse', 'Event log'),
      perm: 'platform.diagnostics',
      render: () => <EventsPanel />,
    },
    {
      id: 'rules',
      path: '/app/platform/alerts/rules',
      label: tr('Benachrichtigungen', 'Notifications'),
      perm: 'platform.diagnostics',
      render: () => <RulesPanel />,
    },
    {
      id: 'mine',
      path: '/app/platform/alerts/mine',
      label: tr('Meine Warnungen', 'My alerts'),
      perm: 'platform.diagnostics',
      render: () => <MyAlertsCard />,
    },
    {
      id: 'settings',
      path: '/app/platform/alerts/settings',
      label: tr('Einstellungen', 'Settings'),
      perm: 'platform.settings',
      render: () => <SettingsSection section="alerts" />,
    },
  ],
}))
