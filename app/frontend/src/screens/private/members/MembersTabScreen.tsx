import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useT } from '@/locales/i18n'
import { PageHead, Tabs } from '@/components/ui'
import { useAuth, useData } from '@/context/AppContext'
import { useNavCounts } from '@/data/lists'
import { MembersTab } from '@/screens/private/members/MembersTab'
import { FunctionsTab } from '@/screens/private/members/FunctionsTab'
import { ApplicationsTab } from '@/screens/private/members/ApplicationsTab'
import { TiersTab } from '@/screens/private/members/TiersTab'

/** Members with functions, applications and tiers as tabs of one screen. */
export function MembersTabScreen() {
  const { t } = useT()
  const location = useLocation()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()
  const { modules } = useData()
  const counts = useNavCounts()

  // The path may start with the club's slug: /<club>/app/members/<tab>.
  const path = (location.pathname.split('/app/members')[1] ?? '').replace('/', '')
  const tab = path === '' ? 'all' : path

  const tabs = [
    { id: 'all', label: t('shell.nav.members', 'Mitglieder') },
    { id: 'functions', label: t('shell.nav.functions', 'Funktionen') },
    {
      id: 'applications',
      label: t('shell.nav.applications', 'Anträge'),
      count: counts.applications,
    },
    { id: 'tiers', label: t('shell.nav.membershipTiers', 'Stufen') },
  ].filter(
    (tb) =>
      (tb.id === 'all' && hasPermission('members.members.read')) ||
      (tb.id === 'functions' &&
        modules.functions &&
        hasPermission('functions.functions.read')) ||
      (tb.id === 'applications' && hasPermission('applications.applications.read')) ||
      (tb.id === 'tiers' && hasPermission('tiers.tiers.read')),
  )

  // Someone who may only see, say, the tiers lands on that tab.
  if (tab === 'all' && tabs.length > 0 && tabs[0].id !== 'all')
    return <Navigate to={`/app/members/${tabs[0].id}`} replace />

  return (
    <div>
      <PageHead title={t('shell.nav.members', 'Mitglieder')} />
      {tabs.length > 1 && (
        <Tabs
          tabs={tabs}
          activeTab={tab}
          onTabChange={(id) => navigate(`/app/members${id === 'all' ? '' : '/' + id}`)}
        />
      )}
      {tab === 'all' && <MembersTab />}
      {tab === 'functions' && <FunctionsTab />}
      {tab === 'applications' && <ApplicationsTab />}
      {tab === 'tiers' && <TiersTab />}
    </div>
  )
}
