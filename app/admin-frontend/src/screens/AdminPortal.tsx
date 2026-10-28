import { useLocation } from 'react-router-dom'
import { PageHead } from '@/components/ui'
import { TenantsTab } from '@/screens/TenantsTab'
import { TenantRequestsTab } from '@/screens/TenantRequestsTab'
import { GlobalAuditTab } from '@/screens/GlobalAuditTab'
import { RolesTab } from '@/screens/RolesTab'
import { MarketplaceTab } from '@/screens/MarketplaceTab'
import { useAdmin } from '@/context/AdminContext'
import { useLang } from '@/lang'

/** One page per sidebar entry; the sidebar is the only navigation. */
export function AdminPortal() {
  const location = useLocation()
  const { hasGlobalPermission } = useAdmin()
  const { tr } = useLang()
  const path = location.pathname

  if (path === '/app/requests')
    return (
      <>
        <PageHead
          title={tr('Meine Anfragen', 'My requests')}
          desc={tr(
            'Beantrage einen neuen Verein auf Hubra und verfolge den Stand deiner Anfragen.',
            'Request a new club on Hubra and follow the status of your requests.',
          )}
        />
        <TenantRequestsTab />
      </>
    )
  if (path === '/app/audit' && hasGlobalPermission('audit.read'))
    return (
      <>
        <PageHead
          title={tr('Audit-Log', 'Audit log')}
          desc={tr('Alle Änderungen auf der Plattform, neueste zuerst.', 'Every change on the platform, newest first.')}
        />
        <GlobalAuditTab />
      </>
    )
  if (path === '/app/roles' && hasGlobalPermission('roles.manage'))
    return (
      <>
        <PageHead
          title={tr('Rollen', 'Roles')}
          desc={tr('Wer auf der Plattform was verwalten darf.', 'Who may manage what on the platform.')}
        />
        <RolesTab />
      </>
    )
  if (path === '/app/plugins' && hasGlobalPermission('plugins.manage'))
    return (
      <>
        <PageHead
          title={tr('Plugin-Katalog', 'Plugin catalogue')}
          desc={tr(
            'Was die Vereine als Plugin bekommen können. Hier geprüfte und installierte Plugins schalten die Vereine selbst unter Einstellungen → Module & Plugins ein.',
            'What clubs can get as a plugin. Plugins vetted and installed here are switched on by each club under Settings → Modules & plugins.',
          )}
        />
        <MarketplaceTab />
      </>
    )
  return (
    <>
      <PageHead
        title={tr('Alle Vereine', 'All clubs')}
        desc={tr('Alle Vereine auf dieser Hubra-Plattform.', 'Every club on this Hubra platform.')}
      />
      <TenantsTab />
    </>
  )
}
