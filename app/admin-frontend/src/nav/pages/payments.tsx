import { IconCreditCard } from '@tabler/icons-react'
import { Stack } from '@mantine/core'
import { tr } from '@/lang'
import { lazyNamed } from '@/lazyNamed'
import { definePage, icon } from '../registry'

const SettingsSection = lazyNamed(() => import('@/screens/platform/SettingsSection'), 'SettingsSection')

export default definePage('services', 40, () => ({
  id: 'payments',
  label: tr('Zahlungen', 'Payments'),
  icon: icon(IconCreditCard),
  desc: tr(
    'Stripe: der Schlüssel des Plattform-Kontos, die Hubra-Gebühr auf Online-Zahlungen der Vereine (Connect) und die Abrechnung der Vereine (Billing).',
    "Stripe: the platform account's key, the Hubra fee on clubs' online payments (Connect) and billing clubs (Billing).",
  ),
  tabs: [
    {
      id: 'stripe',
      path: '/app/platform/payments',
      label: '',
      perm: 'platform.settings',
      render: () => (
        <Stack gap="lg">
          <SettingsSection section="payments" />
          <SettingsSection section="billing" />
        </Stack>
      ),
    },
  ],
}))
