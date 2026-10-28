import { Box, Button, Select, Stack, UnstyledButton } from '@mantine/core'
import {
  IconChevronDown,
  IconUser,
  IconShield,
  IconBuildingBank,
  IconGlobe,
  IconDeviceDesktop,
} from '@tabler/icons-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useNav } from '@/context/AppContext'
import { PageHead } from '@/components/ui'
import { useT } from '@/locales/i18n'
import { AccountSettingsProfileTab } from './AccountSettingsProfileTab'
import { AccountSettingsMembershipTab } from './AccountSettingsMembershipTab'
import { AccountSettingsSecurityTab } from './AccountSettingsSecurityTab'
import { AccountSettingsSessionsTab } from './AccountSettingsSessionsTab'
import { AccountSettingsDevicesTab } from './AccountSettingsDevicesTab'
import { AccountSettingsLanguageTab } from './AccountSettingsLanguageTab'

type SettingsTab =
  | 'profile'
  | 'membership'
  | 'security'
  | 'sessions'
  | 'devices'
  | 'language'

const tabs: {
  id: SettingsTab
  labelKey: string
  labelDefault: string
  icon: React.ReactNode
}[] = [
  {
    id: 'profile',
    labelKey: 'account.profile.tab',
    labelDefault: 'Profil',
    icon: <IconUser size={16} />,
  },
  {
    id: 'membership',
    labelKey: 'account.membership.tab',
    labelDefault: 'Mitgliedschaft',
    icon: <IconBuildingBank size={16} />,
  },
  {
    id: 'security',
    labelKey: 'account.securityTab',
    labelDefault: 'Sicherheit',
    icon: <IconShield size={16} />,
  },
  {
    id: 'sessions',
    labelKey: 'account.sessionsTab',
    labelDefault: 'Sitzungen',
    icon: <IconDeviceDesktop size={16} />,
  },
  {
    id: 'devices',
    labelKey: 'account.devicesTab',
    labelDefault: 'Geräte',
    icon: <IconDeviceDesktop size={16} />,
  },
  {
    id: 'language',
    labelKey: 'account.language.tab',
    labelDefault: 'Spraach',
    icon: <IconGlobe size={16} />,
  },
]

export function AccountSettingsScreen() {
  const { t } = useT()
  const { go } = useNav()
  const location = useLocation()
  const navigate = useNavigate()
  const tab = (location.pathname
    .replace('/app/account/settings', '')
    .replace('/', '') || 'profile') as SettingsTab

  return (
    <div>
      <PageHead
        title={t('account.settings.title', 'Kontoeinstellungen')}
        actions={
          <Button variant="subtle" onClick={() => go('/app/account')}>
            {'\u2190'} {t('account.myAccount', 'Mein Konto')}
          </Button>
        }
      />

      <Box hiddenFrom="nav" mb={16}>
        <Select
          data={tabs.map((tab) => ({
            value: tab.id,
            label: t(tab.labelKey, tab.labelDefault),
          }))}
          value={tab}
          onChange={(v) => {
            if (!v) return
            navigate(`/app/account/settings${v === 'profile' ? '' : '/' + v}`)
          }}
          size="sm"
          radius="md"
          checkIconPosition="right"
          rightSection={<IconChevronDown size={14} />}
        />
      </Box>

      <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>
        <Box
          visibleFrom="nav"
          style={{
            width: 200,
            flexShrink: 0,
            position: 'sticky',
            top: 80,
          }}
        >
          <Stack gap={4}>
            {tabs.map((item) => (
              <UnstyledButton
                key={item.id}
                onClick={() =>
                  navigate(
                    `/app/account/settings${
                      item.id === 'profile' ? '' : '/' + item.id
                    }`,
                  )
                }
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '10px 12px',
                  borderRadius: 8,
                  width: '100%',
                  fontSize: 'var(--mantine-font-size-sm)',
                  fontWeight: tab === item.id ? 600 : 400,
                  color:
                    tab === item.id
                      ? 'var(--mantine-color-ink-8)'
                      : 'var(--mantine-color-dimmed)',
                  background:
                    tab === item.id ? 'rgba(116,65,224,.15)' : undefined,
                }}
              >
                {item.icon}
                {t(item.labelKey, item.labelDefault)}
              </UnstyledButton>
            ))}
          </Stack>
        </Box>

        <div
          style={{
            flex: 1,
            maxWidth: 640,
            display: 'flex',
            flexDirection: 'column',
            gap: 16,
          }}
        >
          {tab === 'profile' && <AccountSettingsProfileTab />}
          {tab === 'membership' && <AccountSettingsMembershipTab />}
          {tab === 'security' && <AccountSettingsSecurityTab />}
          {tab === 'sessions' && <AccountSettingsSessionsTab />}
          {tab === 'devices' && <AccountSettingsDevicesTab />}
          {tab === 'language' && <AccountSettingsLanguageTab />}
        </div>
      </div>
    </div>
  )
}
