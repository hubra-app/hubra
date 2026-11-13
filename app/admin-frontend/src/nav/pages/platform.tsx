import { IconSettings } from '@tabler/icons-react'
import { Stack } from '@mantine/core'
import { tr } from '@/lang'
import { lazyNamed } from '@/lazyNamed'
import { definePage, icon } from '../registry'

const SettingsSection = lazyNamed(() => import('@/screens/platform/SettingsSection'), 'SettingsSection')

export default definePage('services', 60, () => ({
  // What every app of the platform links to: legal texts for the
  // sign-up, footers and Checkout, and the support site.
  id: 'platform',
  label: tr('Plattform', 'Platform'),
  icon: icon(IconSettings),
  desc: tr(
    'Was alle Apps verlinken: Datenschutz, Nutzungsbedingungen und Impressum (Anmeldung, Fusszeilen, Checkout) und die Support-Seite.',
    'What every app links to: privacy, terms and imprint (sign-up, footers, Checkout) and the support site.',
  ),
  tabs: [
    {
      id: 'settings',
      path: '/app/platform/general',
      label: '',
      perm: 'platform.settings',
      render: () => (
        <Stack gap="lg">
          <SettingsSection section="legal" />
          <SettingsSection section="support" />
        </Stack>
      ),
    },
  ],
}))
