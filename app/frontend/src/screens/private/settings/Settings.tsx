import { useLocation, useNavigate } from 'react-router-dom'
import { PageHead, Tabs } from '@/components/ui'
import { useAuth } from '@/context/AppContext'
import { useT } from '@/locales/i18n'
import { KVSettingsTab } from '@/screens/private/settings/KVSettingsTab'
import { ModulesTab } from '@/screens/private/settings/ModulesTab'
import { ClubSettingsTab, MembershipSettingsTab } from '@/screens/private/settings/ClubSettingsTab'
import { BankSettingsCard } from '@/screens/private/settings/BankSettingsCard'
import { DomainsTab } from '@/screens/private/settings/DomainsTab'

// The club profile is what most admins come for, so it is the default tab;
// the raw key/value store sits last under "Erweitert". The club settings are
// split by topic so no tab is one long page.
const TABS = [
  { id: 'club', labelKey: 'settings.tabs.club', label: 'Verein', Component: ClubSettingsTab },
  {
    id: 'membership',
    labelKey: 'settings.tabs.membership',
    label: 'Mitgliedschaft',
    Component: MembershipSettingsTab,
  },
  {
    id: 'bank',
    labelKey: 'settings.tabs.bank',
    label: 'Bank & QR-Rechnung',
    Component: BankSettingsCard,
  },
  {
    id: 'modules',
    labelKey: 'settings.tabs.modules',
    label: 'Module & Plugins',
    Component: ModulesTab,
  },
  { id: 'domains', labelKey: 'settings.tabs.domains', label: 'Domains', Component: DomainsTab },
  {
    id: 'advanced',
    labelKey: 'settings.tabs.settings',
    label: 'Erweitert',
    Component: KVSettingsTab,
  },
] as const

export function SettingsScreen() {
  const location = useLocation()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()
  const { t } = useT()

  const canWriteModules = hasPermission('modules.modules.write')
  // The API keeps the club settings to admin roles; a role may still switch modules.
  const canSettings = hasPermission('settings.settings.read')
  const tabs = TABS.filter((tab) => (tab.id === 'modules' ? canWriteModules : canSettings))

  const requested = location.pathname.replace('/app/settings', '').replace('/', '') || 'club'
  const activeTab = tabs.some((tab) => tab.id === requested) ? requested : (tabs[0]?.id ?? 'club')

  const ActiveComponent = tabs.find((tab) => tab.id === activeTab)?.Component ?? ClubSettingsTab

  return (
    <div>
      <PageHead title={t('shell.nav.settings', 'Einstellungen')} />
      <Tabs
        tabs={tabs.map((tab) => ({ id: tab.id, label: t(tab.labelKey, tab.label) }))}
        activeTab={activeTab}
        onTabChange={(id) => navigate(`/app/settings${id === 'club' ? '' : '/' + id}`)}
      />
      <ActiveComponent />
    </div>
  )
}
