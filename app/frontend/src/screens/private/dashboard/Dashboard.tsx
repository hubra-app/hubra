import { useT } from '@/locales/i18n'
import { useLocation } from 'react-router-dom'
import { useNav } from '@/context/AppContext'
import { PageHead, Tabs } from '@/components/ui'
import { AccountDashboardScreen } from '@/screens/private/account/Account'
import { GlobalOverviewScreen } from '@/screens/private/dashboard/DashboardGlobalTab'

export function DashboardScreen() {
  const { t } = useT()
  const location = useLocation()
  const { go } = useNav()

  const activeTab =
    location.pathname === '/app/dashboard/global' ? 'overview' : 'account'

  return (
    <div>
      <PageHead title={t('dashboard.title')} />
      <Tabs
        tabs={[
          { id: 'account', label: t('dashboard.tabs.account') },
          { id: 'overview', label: t('dashboard.tabs.overview') },
        ]}
        activeTab={activeTab}
        onTabChange={(id) =>
          go(id === 'overview' ? '/app/dashboard/global' : '/app/dashboard')
        }
      />
      {activeTab === 'account' ? (
        <AccountDashboardScreen />
      ) : (
        <GlobalOverviewScreen />
      )}
    </div>
  )
}
