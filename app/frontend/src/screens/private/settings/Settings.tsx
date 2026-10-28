import { useLocation, useNavigate } from 'react-router-dom'
import { PageHead, Tabs } from '@/components/ui'
import { useAuth } from '@/context/AppContext'
import { KVSettingsTab } from '@/screens/private/settings/KVSettingsTab'
import { ModulesTab } from '@/screens/private/settings/ModulesTab'
import { ClubSettingsTab } from '@/screens/private/settings/ClubSettingsTab'
import { DomainsTab } from '@/screens/private/settings/DomainsTab'

const TABS = [
  { id: 'settings', label: 'Settings', Component: KVSettingsTab },
  { id: 'modules', label: 'Modules', Component: ModulesTab },
  { id: 'club', label: 'Club', Component: ClubSettingsTab },
  { id: 'domains', label: 'Domains', Component: DomainsTab },
] as const

export function SettingsScreen() {
  const location = useLocation()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()

  const canWriteModules = hasPermission('modules.modules.write')
  const tabs = TABS.filter((tab) => tab.id !== 'modules' || canWriteModules)

  const activeTab =
    location.pathname.replace('/app/settings', '').replace('/', '') ||
    'settings'

  const ActiveComponent =
    tabs.find((tab) => tab.id === activeTab)?.Component ?? KVSettingsTab

  return (
    <div>
      <PageHead title="Settings" />
      <Tabs
        tabs={tabs.map((tab) => ({ id: tab.id, label: tab.label }))}
        activeTab={activeTab}
        onTabChange={(id) =>
          navigate(`/app/settings${id === 'settings' ? '' : '/' + id}`)
        }
      />
      <ActiveComponent />
    </div>
  )
}
