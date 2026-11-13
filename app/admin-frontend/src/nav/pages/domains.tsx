import { IconWorldWww } from '@tabler/icons-react'
import { tr } from '@/lang'
import { lazyNamed } from '@/lazyNamed'
import { definePage, icon } from '../registry'

const SettingsSection = lazyNamed(() => import('@/screens/platform/SettingsSection'), 'SettingsSection')

export default definePage('services', 30, () => ({
  id: 'domains',
  label: tr('Vereinsdomains', 'Club domains'),
  icon: icon(IconWorldWww),
  desc: tr(
    'Eigene Domains der Vereine: Zertifikat und Ingress pro bestätigter Domain, und der Notschalter.',
    "Clubs' own domains: certificate and Ingress per verified domain, and the kill switch.",
  ),
  tabs: [
    {
      id: 'serving',
      path: '/app/platform/domains',
      label: '',
      perm: 'platform.settings',
      render: () => <SettingsSection section="domains" />,
    },
  ],
}))
