import { IconKey } from '@tabler/icons-react'
import { tr } from '@/lang'
import { lazyNamed } from '@/lazyNamed'
import { definePage, icon } from '../registry'

const RolesTab = lazyNamed(() => import('@/screens/RolesTab'), 'RolesTab')
const PermissionsPanel = lazyNamed(() => import('@/screens/platform/Diagnostics'), 'PermissionsPanel')

export default definePage('access', 10, () => ({
  id: 'roles',
  label: tr('Rollen', 'Roles'),
  icon: icon(IconKey),
  desc: tr('Wer auf der Plattform was verwalten darf.', 'Who may manage what on the platform.'),
  tabs: [
    {
      id: 'platform',
      path: '/app/roles',
      label: tr('Plattform-Rollen', 'Platform roles'),
      perm: 'roles.manage',
      render: () => <RolesTab />,
    },
    {
      id: 'api',
      path: '/app/roles/api',
      label: tr('API-Berechtigungen', 'API permissions'),
      perm: 'platform.diagnostics',
      desc: tr(
        'Welche Berechtigung jede Route der Vereins-API verlangt.',
        'Which permission each route of the club API needs.',
      ),
      render: () => <PermissionsPanel />,
    },
  ],
}))
