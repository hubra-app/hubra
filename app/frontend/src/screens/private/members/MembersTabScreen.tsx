import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useT } from '@/locales/i18n'
import { PageHead, Tabs } from '@/components/ui'
import { useAuth, useData } from '@/context/AppContext'
import { MembersTab } from '@/screens/private/members/MembersTab'
import { FunctionsTab } from '@/screens/private/members/FunctionsTab'
import { ApplicationsTab } from '@/screens/private/members/ApplicationsTab'
import { TiersTab } from '@/screens/private/members/TiersTab'

/**
 * Members with functions and tiers as tabs of one screen. Applications are a
 * to-do list with a count in the sidebar, so they keep their own page.
 */
export function MembersTabScreen() {
  const { t } = useT()
  const location = useLocation()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()
  const { modules } = useData()

  // The path may start with the club's slug: /<club>/app/members/<tab>.
  const path = (location.pathname.split('/app/members')[1] ?? '').replace('/', '')
  const tab = path === '' ? 'all' : path

  const tabs = [
    { id: 'all', label: t('shell.nav.members', 'Mitglieder') },
    { id: 'functions', label: t('shell.nav.functions', 'Funktionen') },
    { id: 'tiers', label: t('shell.nav.membershipTiers', 'Stufen') },
  ].filter(
    (tb) =>
      (tb.id === 'all' && hasPermission('members.members.read')) ||
      (tb.id === 'functions' &&
        modules.functions &&
        hasPermission('functions.functions.read')) ||
      (tb.id === 'tiers' && hasPermission('tiers.tiers.read')),
  )

  // Someone who may only see, say, the tiers lands on that tab.
  if (tab === 'all' && tabs.length > 0 && tabs[0].id !== 'all')
    return <Navigate to={`/app/members/${tabs[0].id}`} replace />

  if (tab === 'applications')
    return (
      <div>
        <PageHead title={t('shell.nav.applications', 'Anträge')} />
        <ApplicationsTab />
      </div>
    )

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
      {tab === 'tiers' && <TiersTab />}
    </div>
  )
}
