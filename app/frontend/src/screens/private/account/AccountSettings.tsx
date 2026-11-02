import { Button } from '@mantine/core'
import { useLocation, useNavigate } from 'react-router-dom'
import { useNav } from '@/context/AppContext'
import { PageHead, Tabs } from '@/components/ui'
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
}[] = [
  {
    id: 'profile',
    labelKey: 'account.club.tab',
    labelDefault: 'Im Verein',
  },
  {
    id: 'membership',
    labelKey: 'account.membership.tab',
    labelDefault: 'Mitgliedschaft',
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

      {/* The same tabs as the other pages (pills on phones). */}
      <Tabs
        tabs={tabs.map((item) => ({ id: item.id, label: t(item.labelKey, item.labelDefault) }))}
        activeTab={tab}
        onTabChange={(id) => navigate(`/app/account/settings${id === 'profile' ? '' : '/' + id}`)}
      />

      <div
        style={{
          // Lets the cards shrink to a phone's width instead of overflowing.
          minWidth: 0,
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
  )
}
