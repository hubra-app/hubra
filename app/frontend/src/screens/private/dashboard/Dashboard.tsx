import { useT } from '@/locales/i18n'
import { useLocation } from 'react-router-dom'
import { useAuth, useNav } from '@/context/AppContext'
import { PageHead, Tabs } from '@/components/ui'
import { AccountDashboardScreen } from '@/screens/private/account/Account'
import { GlobalOverviewScreen } from '@/screens/private/dashboard/DashboardGlobalTab'

export function DashboardScreen() {
  const { t } = useT()
  const location = useLocation()
  const { go } = useNav()
  const { isAdmin, hasPermission } = useAuth()
  // People who run the club start on the club overview, everyone else on
  // their own events and polls; both tabs have their own address too.
  const runsClub =
    isAdmin ||
    hasPermission('members.members.update') ||
    hasPermission('finance.transactions.read')

  const activeTab =
    location.pathname === '/app/dashboard/global'
      ? 'overview'
      : location.pathname === '/app/dashboard/me' || !runsClub
        ? 'account'
        : 'overview'

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
          go(id === 'overview' ? '/app/dashboard/global' : '/app/dashboard/me')
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
