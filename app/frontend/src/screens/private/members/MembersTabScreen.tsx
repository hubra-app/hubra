import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useT } from '@/locales/i18n'
import { PageHead, Tabs } from '@/components/ui'
import { useAuth, useData } from '@/context/AppContext'
import { MembersTab } from '@/screens/private/members/MembersTab'
import { FunctionsTab } from '@/screens/private/members/FunctionsTab'
import { ApplicationsTab } from '@/screens/private/members/ApplicationsTab'
import { TiersTab } from '@/screens/private/members/TiersTab'
import { StatsTab } from '@/screens/private/members/StatsTab'
import { GroupsScreen } from '@/screens/private/members/Groups'

/**
 * Members with what belongs to them as tabs of one screen: functions, tiers,
 * groups and the statistics. Groups keep their address (/app/groups).
 * Applications are a to-do list with a count in the sidebar, so they keep
 * their own page.
 */
const tabPath = (id: string) =>
  id === 'groups' ? '/app/groups' : `/app/members${id === 'all' ? '' : '/' + id}`

export function MembersTabScreen() {
  const { t } = useT()
  const location = useLocation()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()
  const { modules } = useData()

  // The path may start with the club's slug: /<club>/app/members/<tab>.
  const inGroups = /\/app\/groups\/?$/.test(location.pathname)
  const path = (location.pathname.split('/app/members')[1] ?? '').replace('/', '')
  const tab = inGroups ? 'groups' : path === '' ? 'all' : path

  const tabs = [
    { id: 'all', label: t('shell.nav.members', 'Mitglieder') },
    { id: 'functions', label: t('shell.nav.functions', 'Funktionen') },
    { id: 'tiers', label: t('shell.nav.membershipTiers', 'Stufen') },
    { id: 'groups', label: t('shell.nav.groups', 'Gruppen') },
    { id: 'stats', label: t('members.stats.tab', 'Statistik') },
  ].filter(
    (tb) =>
      (tb.id === 'all' && hasPermission('members.members.read')) ||
      (tb.id === 'functions' &&
        modules.functions &&
        hasPermission('functions.functions.read')) ||
      (tb.id === 'tiers' && hasPermission('tiers.tiers.read')) ||
      (tb.id === 'groups' && modules.groups && hasPermission('groups.groups.read')) ||
      (tb.id === 'stats' && hasPermission('members.members.read')),
  )

  // Someone who may only see, say, the tiers lands on that tab.
  if (tab === 'all' && tabs.length > 0 && tabs[0].id !== 'all')
    return <Navigate to={tabPath(tabs[0].id)} replace />

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
          onTabChange={(id) => navigate(tabPath(id))}
        />
      )}
      {tab === 'all' && <MembersTab />}
      {tab === 'functions' && <FunctionsTab />}
      {tab === 'tiers' && <TiersTab />}
      {tab === 'groups' && <GroupsScreen embedded />}
      {tab === 'stats' && <StatsTab />}
    </div>
  )
}
