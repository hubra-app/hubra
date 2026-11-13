import { IconWallet } from '@tabler/icons-react'
import { tr } from '@/lang'
import { lazyNamed } from '@/lazyNamed'
import { definePage, icon } from '../registry'

const SettingsSection = lazyNamed(() => import('@/screens/platform/SettingsSection'), 'SettingsSection')

export default definePage('services', 50, () => ({
  id: 'wallet',
  label: tr('Google Wallet', 'Google Wallet'),
  icon: icon(IconWallet),
  desc: tr(
    'Der Mitgliederausweis als Pass in Google Wallet: Aussteller-Konto, Klasse und Schlüssel. Hubra stellt für alle Vereine aus.',
    'The member badge as a Google Wallet pass: issuer account, class and key. Hubra issues for every club.',
  ),
  tabs: [
    {
      id: 'settings',
      path: '/app/platform/wallet',
      label: '',
      perm: 'platform.settings',
      render: () => <SettingsSection section="wallet" />,
    },
  ],
}))
