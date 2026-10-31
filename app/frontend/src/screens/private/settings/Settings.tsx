import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { PageHead, Tabs } from '@/components/ui'
import { useAuth } from '@/context/AppContext'
import { useT } from '@/locales/i18n'
import { KVSettingsTab } from '@/screens/private/settings/KVSettingsTab'
import { ModulesTab } from '@/screens/private/settings/ModulesTab'
import { ClubSettingsTab, MembershipSettingsTab } from '@/screens/private/settings/ClubSettingsTab'
import { BankSettingsCard } from '@/screens/private/settings/BankSettingsCard'
import { DomainsTab } from '@/screens/private/settings/DomainsTab'
import { AuditLogScreen } from '@/screens/private/system/AuditLog'
import { RolesTab } from '@/screens/private/system/RolesTab'

const AuditLogTab = () => <AuditLogScreen embedded />

// The club profile is what most admins come for, so it is the default tab;
// the raw key/value store sits last under "Erweitert". The club settings are
// split by topic so no tab is one long page. Roles and the audit log keep
// their own addresses but sit here as tabs, so the sidebar's "Verwaltung" is
// one entry.
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
  { id: 'roles', labelKey: 'shell.nav.permissions', label: 'Rollen', Component: RolesTab },
  { id: 'audit', labelKey: 'shell.nav.auditLog', label: 'Protokoll', Component: AuditLogTab },
  {
    id: 'advanced',
    labelKey: 'settings.tabs.settings',
    label: 'Erweitert',
    Component: KVSettingsTab,
  },
] as const

// Tabs whose page lives outside /app/settings.
const TAB_PATHS: Record<string, string> = { roles: '/app/system', audit: '/app/audit-log' }

const tabPath = (id: string) => TAB_PATHS[id] ?? `/app/settings${id === 'club' ? '' : '/' + id}`

export function SettingsScreen() {
  const location = useLocation()
  const navigate = useNavigate()
  const { hasPermission } = useAuth()
  const { t } = useT()

  const canWriteModules = hasPermission('modules.modules.write')
  // The API keeps the club settings to admin roles; a role may still switch modules.
  const canSettings = hasPermission('settings.settings.read')
  const tabs = TABS.filter((tab) =>
    tab.id === 'modules'
      ? canWriteModules
      : tab.id === 'roles'
        ? hasPermission('roles.roles.create')
        : tab.id === 'audit'
          ? hasPermission('audit.audit.read')
          : canSettings,
  )

  // The path may start with the club's slug: /<club>/app/settings/<tab>.
  const { pathname } = location
  const outside = Object.entries(TAB_PATHS).find(([, path]) => pathname.includes(path))
  const requested =
    outside?.[0] ?? ((pathname.split('/app/settings')[1] ?? '').replace('/', '') || 'club')
  const activeTab = tabs.some((tab) => tab.id === requested) ? requested : (tabs[0]?.id ?? 'club')

  // Someone who may only see, say, the audit log lands on that tab.
  if (requested === 'club' && tabs.length > 0 && tabs[0].id !== 'club')
    return <Navigate to={tabPath(tabs[0].id)} replace />

  const ActiveComponent = tabs.find((tab) => tab.id === activeTab)?.Component ?? ClubSettingsTab

  return (
    <div>
      <PageHead title={t('shell.nav.settings', 'Einstellungen')} />
      <Tabs
        tabs={tabs.map((tab) => ({ id: tab.id, label: t(tab.labelKey, tab.label) }))}
        activeTab={activeTab}
        onTabChange={(id) => navigate(tabPath(id))}
      />
      <ActiveComponent />
    </div>
  )
}
