import { IconDatabase } from '@tabler/icons-react'
import { tr } from '@/lang'
import { lazyNamed } from '@/lazyNamed'
import { definePage, icon } from '../registry'

const Backups = lazyNamed(() => import('@/screens/platform/Backups'), 'Backups')
const BackupsDesc = lazyNamed(() => import('@/screens/platform/Backups'), 'BackupsDesc')
const SettingsSection = lazyNamed(() => import('@/screens/platform/SettingsSection'), 'SettingsSection')

export default definePage('operations', 30, () => ({
  id: 'backups',
  label: tr('Backups', 'Backups'),
  icon: icon(IconDatabase),
  desc: <BackupsDesc />,
  tabs: [
    {
      id: 'list',
      path: '/app/platform/backups',
      label: tr('Backups', 'Backups'),
      perm: 'backups.manage',
      render: () => <Backups />,
    },
    {
      id: 'settings',
      path: '/app/platform/backups/settings',
      label: tr('Einstellungen', 'Settings'),
      perm: 'platform.settings',
      desc: tr(
        'Wohin die verschlüsselten Backups und die Dateien der Vereine gehen und wie lange Backups bleiben.',
        "Where the encrypted backups and the clubs' files go, and how long backups are kept.",
      ),
      render: () => (
        <>
          <SettingsSection section="backups" />
          <SettingsSection section="backup-retention" />
          <SettingsSection section="files" />
        </>
      ),
    },
  ],
}))
