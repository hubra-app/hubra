import { IconBrandDiscord } from '@tabler/icons-react'
import { Stack } from '@mantine/core'
import { tr } from '@/lang'
import { lazyNamed } from '@/lazyNamed'
import { definePage, icon } from '../registry'

const DiscordPanel = lazyNamed(() => import('@/screens/platform/DiscordStatus'), 'DiscordPanel')
const DiscordClubsPanel = lazyNamed(() => import('@/screens/platform/DiscordClubs'), 'DiscordClubsPanel')
const SettingsSection = lazyNamed(() => import('@/screens/platform/SettingsSection'), 'SettingsSection')

export default definePage('services', 20, () => ({
  id: 'discord',
  label: 'Discord',
  icon: icon(IconBrandDiscord),
  desc: tr(
    'Die Hubra-App auf Discord: ob der Bot läuft, alle Vereinsserver, die Zugangsdaten und die Kanäle der Plattform.',
    'The Hubra app on Discord: whether the bot runs, every club server, its credentials and the platform channels.',
  ),
  tabs: [
    {
      id: 'status',
      path: '/app/platform/discord',
      label: tr('Status', 'Status'),
      perm: 'platform.diagnostics',
      render: () => <DiscordPanel />,
    },
    {
      id: 'clubs',
      path: '/app/platform/discord/clubs',
      label: tr('Vereinsserver', 'Club servers'),
      perm: 'platform.diagnostics',
      render: () => <DiscordClubsPanel />,
    },
    {
      id: 'settings',
      path: '/app/platform/discord/settings',
      label: tr('Einstellungen', 'Settings'),
      perm: 'platform.settings',
      desc: tr(
        'Die Zugangsdaten der Hubra-App auf Discord und die Kanäle der Plattform.',
        "The Hubra app's Discord credentials and the platform channels.",
      ),
      render: () => (
        <Stack gap="lg">
          <SettingsSection section="discord-app" />
          <SettingsSection section="discord-channels" />
        </Stack>
      ),
    },
  ],
}))
