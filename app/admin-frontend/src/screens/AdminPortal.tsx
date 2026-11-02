import { useLocation } from 'react-router-dom'
import { PageHead } from '@/components/ui'
import { TenantsTab } from '@/screens/TenantsTab'
import { TenantRequestsTab } from '@/screens/TenantRequestsTab'
import { GlobalAuditTab } from '@/screens/GlobalAuditTab'
import { SupportSessionsTab } from '@/screens/SupportSessionsTab'
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

  if (path === '/app/requests' && hasGlobalPermission('requests.read.all'))
    return (
      <>
        <PageHead
          title={tr('Vereinsanfragen', 'Club requests')}
          desc={tr(
            'Neue Vereine, die Leute auf der Anmeldeseite beantragt haben. Hier prüfst du sie und gibst sie frei.',
            'New clubs people asked for on the sign-in site. Review and approve them here.',
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
          desc={tr(
            'Alle Änderungen auf der Plattform und in allen Vereinen, neueste zuerst. Suchen, filtern und als CSV exportieren.',
            'Every change on the platform and in every club, newest first. Search, filter and export as CSV.',
          )}
        />
        <GlobalAuditTab />
      </>
    )
  if (path === '/app/support' && hasGlobalPermission('audit.read'))
    return (
      <>
        <PageHead
          title={tr('Support-Zugriffe', 'Support access')}
          desc={tr(
            'Wann Plattform-Admins einen Verein als eines seiner Mitglieder geöffnet haben: wer, warum, wie lange. Laufende Sitzungen lassen sich hier beenden.',
            'When platform admins opened a club as one of its members: who, why and for how long. Running sessions can be ended here.',
          )}
        />
        <SupportSessionsTab />
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
