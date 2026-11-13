import { IconHeartbeat } from '@tabler/icons-react'
import { tr } from '@/lang'
import { lazyNamed } from '@/lazyNamed'
import { definePage, icon } from '../registry'

const HealthPanel = lazyNamed(() => import('@/screens/platform/Diagnostics'), 'HealthPanel')
const JobsPanel = lazyNamed(() => import('@/screens/platform/Jobs'), 'JobsPanel')
const ErrorsPanel = lazyNamed(() => import('@/screens/platform/Errors'), 'ErrorsPanel')
const PerformancePanel = lazyNamed(() => import('@/screens/platform/Performance'), 'PerformancePanel')
const ApiErrorsPanel = lazyNamed(() => import('@/screens/platform/ApiErrors'), 'ApiErrorsPanel')
const SettingsSection = lazyNamed(() => import('@/screens/platform/SettingsSection'), 'SettingsSection')

export default definePage('operations', 20, () => ({
  id: 'diagnostics',
  label: tr('Diagnose', 'Diagnostics'),
  icon: icon(IconHeartbeat),
  desc: tr(
    'Wie es den Diensten geht, welche Fehler auftreten, wie schnell die API antwortet und was im Hintergrund läuft.',
    'How the services are doing, which errors happen, how fast the API answers and what runs in the background.',
  ),
  tabs: [
    {
      id: 'health',
      path: '/app/platform/diagnostics',
      label: tr('Systemzustand', 'System health'),
      perm: 'platform.diagnostics',
      render: () => <HealthPanel />,
    },
    {
      id: 'errors',
      path: '/app/platform/diagnostics/errors',
      label: tr('Fehler', 'Errors'),
      perm: 'platform.diagnostics',
      render: () => <ErrorsPanel />,
    },
    {
      id: 'api-errors',
      path: '/app/platform/diagnostics/api-errors',
      label: tr('API-Fehler', 'API errors'),
      perm: 'platform.diagnostics',
      render: () => <ApiErrorsPanel />,
    },
    {
      id: 'performance',
      path: '/app/platform/diagnostics/performance',
      label: tr('Leistung', 'Performance'),
      perm: 'platform.diagnostics',
      render: () => <PerformancePanel />,
    },
    {
      id: 'jobs',
      path: '/app/platform/diagnostics/jobs',
      label: tr('Hintergrundjobs', 'Background jobs'),
      perm: 'platform.diagnostics',
      render: () => <JobsPanel />,
    },
    {
      id: 'settings',
      path: '/app/platform/diagnostics/settings',
      label: tr('Einstellungen', 'Settings'),
      perm: 'platform.settings',
      render: () => <SettingsSection section="performance" />,
    },
  ],
}))
