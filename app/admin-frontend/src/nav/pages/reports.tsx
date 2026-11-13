import { IconLifebuoy } from '@tabler/icons-react'
import { tr } from '@/lang'
import { lazyNamed } from '@/lazyNamed'
import { definePage, icon } from '../registry'

const SupportCases = lazyNamed(() => import('@/screens/platform/Support'), 'SupportCases')

export default definePage('clubs', 30, () => ({
  id: 'reports',
  label: tr('Meldungen & Ideen', 'Reports & ideas'),
  icon: icon(IconLifebuoy),
  ownHead: true,
  tabs: [
    {
      id: 'list',
      path: '/app/reports',
      label: '',
      perm: 'support.cases',
      render: () => <SupportCases />,
    },
  ],
}))
