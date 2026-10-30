import { useLocation } from 'react-router-dom'
import { useT } from '@/locales/i18n'
import { PageHead } from '@/components/ui'
import { MembersTab } from '@/screens/private/members/MembersTab'
import { FunctionsTab } from '@/screens/private/members/FunctionsTab'
import { ApplicationsTab } from '@/screens/private/members/ApplicationsTab'
import { TiersTab } from '@/screens/private/members/TiersTab'

/** Members, functions, applications and tiers: each its own sidebar page. */
export function MembersTabScreen() {
  const { t } = useT()
  const location = useLocation()
  const page = location.pathname.replace(/^\/app\/members\/?/, '') || 'all'

  const titles: Record<string, string> = {
    all: t('shell.nav.members', 'Mitglieder'),
    functions: t('shell.nav.functions', 'Funktionen'),
    applications: t('shell.nav.applications', 'Anträge'),
    tiers: t('shell.nav.membershipTiers', 'Stufen'),
  }

  return (
    <div>
      <PageHead title={titles[page] ?? titles.all} />
      {page === 'all' && <MembersTab />}
      {page === 'functions' && <FunctionsTab />}
      {page === 'applications' && <ApplicationsTab />}
      {page === 'tiers' && <TiersTab />}
    </div>
  )
}
