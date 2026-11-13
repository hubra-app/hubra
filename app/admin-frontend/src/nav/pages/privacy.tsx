import { IconShieldLock } from '@tabler/icons-react'
import { tr } from '@/lang'
import { lazyNamed } from '@/lazyNamed'
import { definePage, icon } from '../registry'

const DataRequestsPanel = lazyNamed(() => import('@/screens/DataRequests'), 'DataRequestsPanel')

export default definePage('access', 40, () => ({
  id: 'privacy',
  label: tr('Datenschutz', 'Data protection'),
  icon: icon(IconShieldLock),
  desc: tr(
    'Wenn jemand eine Kopie seiner Daten in einem Verein will oder sie gelöscht haben möchte. Frist 30 Tage; hier steht, wer jede Anfrage wann erledigt hat.',
    'When someone wants a copy of their data in a club, or wants it deleted. 30-day deadline; this records who handled each request and when.',
  ),
  tabs: [
    {
      id: 'requests',
      path: '/app/privacy',
      label: '',
      perm: 'privacy.requests',
      render: () => <DataRequestsPanel />,
    },
  ],
}))
