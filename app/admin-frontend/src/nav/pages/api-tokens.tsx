import { IconPlugConnected } from '@tabler/icons-react'
import { Stack } from '@mantine/core'
import { tr } from '@/lang'
import { lazyNamed } from '@/lazyNamed'
import { definePage, icon } from '../registry'

const SettingsSection = lazyNamed(() => import('@/screens/platform/SettingsSection'), 'SettingsSection')
const AllApiTokens = lazyNamed(() => import('@/screens/platform/ApiTokens'), 'AllApiTokens')
const PlatformTokensPage = lazyNamed(() => import('@/screens/platform/ApiTokens'), 'PlatformTokensPage')
const OAuthApps = lazyNamed(() => import('@/screens/platform/OAuthApps'), 'OAuthApps')

export default definePage('access', 20, () => ({
  id: 'api-tokens',
  label: tr('API-Tokens', 'API tokens'),
  icon: icon(IconPlugConnected),
  desc: tr(
    'Lesende Tokens für Skripte und den Claude-Connector, und Apps mit OAuth-Anmeldung.',
    'Read-only tokens for scripts and the Claude connector, and apps that sign in with OAuth.',
  ),
  tabs: [
    {
      id: 'mine',
      path: '/app/api-tokens',
      label: tr('Meine Tokens', 'My tokens'),
      render: () => <PlatformTokensPage />,
    },
    {
      id: 'all',
      path: '/app/api-tokens/all',
      label: tr('Alle Tokens', 'All tokens'),
      perm: 'platform.settings',
      render: () => <AllApiTokens />,
    },
    {
      id: 'apps',
      path: '/app/api-tokens/apps',
      label: tr('Apps (OAuth)', 'Apps (OAuth)'),
      perm: 'platform.settings',
      render: () => <OAuthApps />,
    },
    {
      id: 'settings',
      path: '/app/api-tokens/settings',
      label: tr('Einstellungen', 'Settings'),
      perm: 'platform.settings',
      render: () => (
        <Stack gap="lg">
          <SettingsSection section="mcp" />
          <SettingsSection section="oauth" />
        </Stack>
      ),
    },
  ],
}))
