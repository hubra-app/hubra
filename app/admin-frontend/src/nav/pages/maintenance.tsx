import { IconTool } from '@tabler/icons-react'
import { tr } from '@/lang'
import { lazyNamed } from '@/lazyNamed'
import { definePage, icon } from '../registry'

const MaintenancePanel = lazyNamed(() => import('@/screens/platform/Alerts'), 'MaintenancePanel')

export default definePage('operations', 40, () => ({
  id: 'maintenance',
  label: tr('Wartung', 'Maintenance'),
  icon: icon(IconTool),
  desc: tr(
    'Den Wartungsmodus jetzt ein- und ausschalten oder ein Wartungsfenster planen, das die Vereine vorher sehen.',
    'Switch maintenance mode on or off now, or plan a maintenance window clubs see in advance.',
  ),
  tabs: [
    {
      id: 'now',
      path: '/app/platform/maintenance',
      label: '',
      perm: 'platform.diagnostics',
      render: () => <MaintenancePanel />,
    },
  ],
}))
