import { useLocation, useNavigate } from 'react-router-dom'
import { PageHead, Tabs } from '@/components/ui'
import { useAuth } from '@/context/AppContext'
import { useT } from '@/locales/i18n'
import { KVSettingsTab } from '@/screens/private/settings/KVSettingsTab'
import { ModulesTab } from '@/screens/private/settings/ModulesTab'
import { ClubSettingsTab } from '@/screens/private/settings/ClubSettingsTab'
import { DomainsTab } from '@/screens/private/settings/DomainsTab'

// The club profile is what most admins come for, so it is the default tab;
// the raw key/value store sits last under "Erweitert".
const TABS = [
  { id: 'club', labelKey: 'settings.tabs.club', label: 'Verein', Component: ClubSettingsTab },
  { id: 'modules', labelKey: 'settings.tabs.modules', label: 'Module & Plugins', Component: ModulesTab },
  { id: 'domains', labelKey: 'settings.tabs.domains', label: 'Domains', Component: DomainsTab },
  { id: 'advanced', labelKey: 'settings.tabs.settings', label: 'Erweitert', Component: KVSettingsTab },
] as const

export function SettingsScreen() {
  const location = useLocation()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()
  const { t } = useT()

  const canWriteModules = hasPermission('modules.modules.write')
  const tabs = TABS.filter((tab) => tab.id !== 'modules' || canWriteModules)

  const activeTab =
    location.pathname.replace('/app/settings', '').replace('/', '') ||
    'club'

  const ActiveComponent =
    tabs.find((tab) => tab.id === activeTab)?.Component ?? ClubSettingsTab

  return (
    <div>
      <PageHead title={t('shell.nav.settings', 'Einstellungen')} />
      <Tabs
        tabs={tabs.map((tab) => ({ id: tab.id, label: t(tab.labelKey, tab.label) }))}
        activeTab={activeTab}
        onTabChange={(id) =>
          navigate(`/app/settings${id === 'club' ? '' : '/' + id}`)
        }
      />
      <ActiveComponent />
    </div>
  )
}
