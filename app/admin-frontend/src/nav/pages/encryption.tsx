import { IconLock } from '@tabler/icons-react'
import { tr } from '@/lang'
import { lazyNamed } from '@/lazyNamed'
import { definePage, icon } from '../registry'

const PlatformEncryption = lazyNamed(() => import('@/screens/platform/Encryption'), 'PlatformEncryption')

export default definePage('access', 50, () => ({
  id: 'encryption',
  label: tr('Verschlüsselung', 'Encryption'),
  icon: icon(IconLock),
  desc: tr(
    'Die Schlüssel, mit denen Hubra Geheimnisse und Vereinsdaten verschlüsselt.',
    'The keys Hubra encrypts secrets and club data with.',
  ),
  tabs: [
    {
      id: 'keys',
      path: '/app/platform/encryption',
      label: '',
      perm: 'platform.settings',
      render: () => <PlatformEncryption />,
    },
  ],
}))
