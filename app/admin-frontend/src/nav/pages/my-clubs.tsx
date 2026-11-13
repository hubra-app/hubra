import { IconHome } from '@tabler/icons-react'
import { tr } from '@/lang'
import { lazyNamed } from '@/lazyNamed'
import { definePage, icon } from '../registry'

const MyTenantsTab = lazyNamed(() => import('@/screens/MyTenantsTab'), 'MyTenantsTab')

export default definePage('clubs', 10, () => ({
  id: 'my-clubs',
  label: tr('Deine Vereine', 'Clubs you run'),
  icon: icon(IconHome),
  ownHead: true,
  tabs: [{ id: 'list', path: '/app/my-tenants', label: '', render: () => <MyTenantsTab /> }],
}))
