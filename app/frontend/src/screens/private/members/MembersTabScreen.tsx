import { useLocation, useNavigate } from 'react-router-dom'
import { useT } from '@/locales/i18n'
import { PageHead, Tabs } from '@/components/ui'
import { useAuth } from '@/context/AppContext'
import { MembersTab } from '@/screens/private/members/MembersTab'
import { FunctionsTab } from '@/screens/private/members/FunctionsTab'
import { ApplicationsTab } from '@/screens/private/members/ApplicationsTab'
import { TiersTab } from '@/screens/private/members/TiersTab'

export function MembersTabScreen() {
  const { t } = useT()
  const location = useLocation()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()

  const path = location.pathname.replace('/app/members', '').replace('/', '')
  const tab = path === '' ? 'all' : path

  const tabs = [
    { id: 'all', label: t('shell.nav.allMembers') },
    { id: 'functions', label: t('shell.nav.functions') },
    {
      id: 'applications',
      label: t('shell.nav.applications'),
    },
    { id: 'tiers', label: t('shell.nav.membershipTiers') },
  ].filter(
    (tb) =>
      tb.id === 'all' ||
      (tb.id === 'functions' && hasPermission('functions.functions.read')) ||
      (tb.id === 'applications' &&
        hasPermission('applications.applications.read')) ||
      (tb.id === 'tiers' && hasPermission('tiers.tiers.read')),
  )

  return (
    <div>
      <PageHead title={t('shell.nav.members', 'Members')} />
      <Tabs
        tabs={tabs}
        activeTab={tab}
        onTabChange={(id) =>
          navigate(`/app/members${id === 'all' ? '' : '/' + id}`)
        }
      />
      {tab === 'all' && <MembersTab />}
      {tab === 'functions' && <FunctionsTab />}
      {tab === 'applications' && <ApplicationsTab />}
      {tab === 'tiers' && <TiersTab />}
    </div>
  )
}
