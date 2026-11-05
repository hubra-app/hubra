import type { ComponentType } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useT } from '@/locales/i18n'
import { PageHead, Tabs } from '@/components/ui'
import { useAuth } from '@/context/AppContext'
import { MembersTab } from '@/screens/private/members/MembersTab'
import { FunctionsTab } from '@/screens/private/members/FunctionsTab'
import { ApplicationsTab } from '@/screens/private/members/ApplicationsTab'
import { TiersTab } from '@/screens/private/members/TiersTab'
import { StatsTab } from '@/screens/private/members/StatsTab'

/**
 * Members with their statistics as a tab: two views of the same people.
 * Applications, functions and tiers are pages of their own with their own
 * sidebar row.
 */
export function MembersTabScreen() {
  const { t } = useT()
  const location = useLocation()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()

  // The path may start with the club's slug: /<club>/app/members/<tab>.
  const path = (location.pathname.split('/app/members')[1] ?? '').replace('/', '')
  const tab = path === '' ? 'all' : path

  const tabs = hasPermission('members.members.read')
    ? [
        { id: 'all', label: t('shell.nav.members', 'Mitglieder') },
        { id: 'stats', label: t('members.stats.tab', 'Statistik') },
      ]
    : []

  const own: Record<string, [string, string, ComponentType]> = {
    applications: ['shell.nav.applications', 'Anträge', ApplicationsTab],
    functions: ['shell.nav.functions', 'Funktionen', FunctionsTab],
    tiers: ['shell.nav.membershipTiers', 'Stufen', TiersTab],
  }
  if (own[tab]) {
    const [key, fallback, Page] = own[tab]
    return (
      <div>
        <PageHead title={t(key, fallback)} />
        <Page />
      </div>
    )
  }

  // Someone who may only see, say, the tiers lands on that page.
  if (tabs.length === 0) {
    const first = hasPermission('tiers.tiers.read') ? 'tiers' : 'functions'
    return <Navigate to={`/app/members/${first}`} replace />
  }

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
      {tab === 'stats' && <StatsTab />}
    </div>
  )
}
