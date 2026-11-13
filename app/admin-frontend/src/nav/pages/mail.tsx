import { IconMail } from '@tabler/icons-react'
import { Stack } from '@mantine/core'
import { tr } from '@/lang'
import { lazyNamed } from '@/lazyNamed'
import { definePage, icon } from '../registry'

const MailServerPanel = lazyNamed(() => import('@/screens/platform/Diagnostics'), 'MailServerPanel')
const OutboundMailTab = lazyNamed(() => import('@/screens/platform/MailMonitor'), 'OutboundMailTab')
const SettingsSection = lazyNamed(() => import('@/screens/platform/SettingsSection'), 'SettingsSection')

export default definePage('services', 10, () => ({
  id: 'mail',
  label: tr('Mail', 'Mail'),
  icon: icon(IconMail),
  desc: tr(
    'Was Hubra verschickt, über welches Relay und von welchem Absender, und der gemeinsame Mailserver der Vereine.',
    'What Hubra sends, through which relay and from which sender, and the shared mail server of the clubs.',
  ),
  tabs: [
    {
      id: 'outbound',
      path: '/app/platform/mail',
      label: tr('Versand', 'Outbound'),
      perm: 'platform.diagnostics',
      render: () => <OutboundMailTab />,
    },
    {
      id: 'server',
      path: '/app/platform/mail/server',
      label: tr('Mailserver', 'Mail server'),
      perm: 'platform.diagnostics',
      render: () => <MailServerPanel />,
    },
    {
      id: 'settings',
      path: '/app/platform/mail/settings',
      label: tr('Einstellungen', 'Settings'),
      perm: 'platform.settings',
      desc: tr(
        'Über welches Relay Hubra Mails verschickt und von welchem Absender.',
        'Which relay Hubra sends mail through, and from which sender.',
      ),
      render: () => (
        <Stack gap="lg">
          <SettingsSection section="relay" />
          <SettingsSection section="sender" />
        </Stack>
      ),
    },
  ],
}))
