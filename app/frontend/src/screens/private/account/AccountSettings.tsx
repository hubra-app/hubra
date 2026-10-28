import { Box, Button, Select, Stack, UnstyledButton } from '@mantine/core'
import { IconChevronDown, IconUser, IconBuildingBank } from '@tabler/icons-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useNav } from '@/context/AppContext'
import { PageHead } from '@/components/ui'
import { useT } from '@/locales/i18n'
import { AccountSettingsClubTab } from './AccountSettingsClubTab'
import { AccountSettingsMembershipTab } from './AccountSettingsMembershipTab'

// Only what this club adds to the account; the account itself (profile,
// email, password, language, sessions) is on the SSO portal.
type SettingsTab = 'profile' | 'membership'

const tabs: {
  id: SettingsTab
  labelKey: string
  labelDefault: string
  icon: React.ReactNode
}[] = [
  {
    id: 'profile',
    labelKey: 'account.club.tab',
    labelDefault: 'Im Verein',
    icon: <IconUser size={16} />,
  },
  {
    id: 'membership',
    labelKey: 'account.membership.tab',
    labelDefault: 'Mitgliedschaft',
    icon: <IconBuildingBank size={16} />,
  },
]

export function AccountSettingsScreen() {
  const { t } = useT()
  const { go } = useNav()
  const location = useLocation()
  const navigate = useNavigate()
  const tab: SettingsTab = location.pathname.endsWith('/membership') ? 'membership' : 'profile'

  return (
    <div>
      <PageHead
        title={t('account.settings.title', 'Kontoeinstellungen')}
        actions={
          <Button variant="subtle" onClick={() => go('/app/dashboard')}>
            {'\u2190'} {t('shell.nav.dashboard', 'Dashboard')}
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
                  navigate(`/app/account/settings${item.id === 'profile' ? '' : '/' + item.id}`)
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
                    tab === item.id ? 'var(--mantine-color-ink-8)' : 'var(--mantine-color-dimmed)',
                  background: tab === item.id ? 'rgba(116,65,224,.15)' : undefined,
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
          {tab === 'profile' && <AccountSettingsClubTab />}
          {tab === 'membership' && <AccountSettingsMembershipTab />}
        </div>
      </div>
    </div>
  )
}
