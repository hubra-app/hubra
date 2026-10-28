import { NavLink, useLocation } from 'react-router-dom'
import { AppShell, Text, Group, UnstyledButton, Badge } from '@mantine/core'
import {
  IconBuildingCog,
  IconShieldCheck,
  IconLogout,
  IconClipboardList,
  IconKey,
} from '@tabler/icons-react'
import { useAdmin } from '@/context/AdminContext'

export function Shell({ children }: { children: React.ReactNode }) {
  const { logout, impersonation, hasGlobalPermission } = useAdmin()
  const location = useLocation()

  const navItems = [
    ...(hasGlobalPermission('tenants.read')
      ? [{ path: '/app/tenants', label: 'Tenants', icon: <IconBuildingCog size={22} /> }]
      : []),
    { path: '/app/requests', label: 'My Requests', icon: <IconClipboardList size={22} /> },
    ...(hasGlobalPermission('audit.read')
      ? [{ path: '/app/audit', label: 'Audit Log', icon: <IconShieldCheck size={22} /> }]
      : []),
    ...(hasGlobalPermission('roles.manage')
      ? [{ path: '/app/roles', label: 'Roles', icon: <IconKey size={22} /> }]
      : []),
  ]

  return (
    <AppShell
      navbar={{
        width: { base: 220 },
        breakpoint: 'sm',
      }}
      padding="xl"
    >
      <AppShell.Navbar p="md" style={{ background: '#fff' }}>
        <Group gap={10} mb={30} px="sm">
          <div className="logo-mark" />
          <div>
            <Text fw={700} fz="sm" lh={1.2}>
              Club Ops Suite
            </Text>
            <Text fz="xs" c="dimmed">
              Admin Portal
            </Text>
          </div>
        </Group>

        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '10px 12px',
              borderRadius: 8,
              textDecoration: 'none',
              fontWeight: location.pathname.startsWith(item.path) ? 700 : 500,
              color: location.pathname.startsWith(item.path) ? '#181818' : '#6b7480',
              background: location.pathname.startsWith(item.path)
                ? 'rgba(254,206,43,0.12)'
                : 'transparent',
              marginBottom: 4,
            }}
          >
            {item.icon}
            <Text fz="sm">{item.label}</Text>
          </NavLink>
        ))}

        <Group mt="auto" px="sm" style={{ marginTop: 'auto' }}>
          <UnstyledButton
            onClick={logout}
            style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#6b7480' }}
          >
            <IconLogout size={18} />
            <Text fz="sm">Logout</Text>
          </UnstyledButton>
        </Group>
      </AppShell.Navbar>

      {impersonation?.is_impersonating && (
        <div
          style={{
            background: '#fef3c7',
            borderBottom: '1px solid #f59e0b',
            padding: '8px 16px',
            fontSize: 14,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <Badge color="orange" variant="filled" size="sm">
            Impersonating
          </Badge>
          <Text fz="sm" fw={600}>
            Acting in tenant: {impersonation.tenant_slug}
          </Text>
          {impersonation.reason && (
            <Text fz="xs" c="dimmed">
              Reason: {impersonation.reason}
            </Text>
          )}
        </div>
      )}

      <AppShell.Main>{children}</AppShell.Main>
    </AppShell>
  )
}
