import { useLocation, useNavigate } from 'react-router-dom'
import { PageHead, Tabs } from '@/components/ui'
import { TenantsTab } from '@/screens/TenantsTab'
import { MyTenantsTab } from '@/screens/MyTenantsTab'
import { TenantRequestsTab } from '@/screens/TenantRequestsTab'
import { GlobalAuditTab } from '@/screens/GlobalAuditTab'
import { RolesTab } from '@/screens/RolesTab'
import { useAdmin } from '@/context/AdminContext'

export function AdminPortal() {
  const location = useLocation()
  const navigate = useNavigate()
  const { hasGlobalPermission } = useAdmin()

  const tab =
    location.pathname === '/app/audit'
      ? 'audit'
      : location.pathname === '/app/requests'
        ? 'requests'
        : location.pathname === '/app/roles'
          ? 'roles'
          : location.pathname === '/app/my-tenants'
            ? 'my-tenants'
            : 'tenants'

  const tabs = [
    { id: 'my-tenants', label: 'My Spaces' },
    ...(hasGlobalPermission('tenants.read') ? [{ id: 'tenants', label: 'All Tenants' }] : []),
    { id: 'requests', label: 'My Requests' },
    ...(hasGlobalPermission('audit.read') ? [{ id: 'audit', label: 'Audit Log' }] : []),
    ...(hasGlobalPermission('roles.manage') ? [{ id: 'roles', label: 'Roles' }] : []),
  ]

  return (
    <div>
      <PageHead
        eyebrow="Platform"
        title={hasGlobalPermission('tenants.read') ? 'Admin Portal' : 'My Portal'}
      />
      <Tabs
        tabs={tabs}
        activeTab={tab}
        onTabChange={(id) =>
          navigate(
            id === 'tenants'
              ? '/app/tenants'
              : id === 'requests'
                ? '/app/requests'
                : id === 'audit'
                  ? '/app/audit'
                  : id === 'roles'
                    ? '/app/roles'
                    : '/app/my-tenants',
          )
        }
      />
      {tab === 'my-tenants' && <MyTenantsTab />}
      {tab === 'tenants' && hasGlobalPermission('tenants.read') && <TenantsTab />}
      {tab === 'requests' && <TenantRequestsTab />}
      {tab === 'audit' && hasGlobalPermission('audit.read') && <GlobalAuditTab />}
      {tab === 'roles' && hasGlobalPermission('roles.manage') && <RolesTab />}
    </div>
  )
}
