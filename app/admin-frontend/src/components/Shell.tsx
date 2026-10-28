import { useEffect } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { AppShell, Text, Group, UnstyledButton, Badge, Burger, Drawer, Stack } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { SSO_URL } from '@hubra/api-client'
import {
  IconBuildingCog,
  IconHome,
  IconSearch,
  IconShieldCheck,
  IconLogout,
  IconClipboardList,
  IconKey,
  IconPuzzle,
  IconSettings,
  IconPlus,
} from '@tabler/icons-react'
import { useAdmin } from '@/context/AdminContext'

interface NavItem {
  label: string
  icon: React.ReactNode
  /** In-app route… */
  path?: string
  /** …or a page of another Hubra app. */
  href?: string
}

function Brand() {
  return (
    <Group gap={10} wrap="nowrap">
      <div className="logo-mark" />
      <div>
        <Text fz={20} className="wordmark">
          hubra
        </Text>
        <Text fz="xs" c="dimmed">
          Admin Portal
        </Text>
      </div>
    </Group>
  )
}

interface NavSection {
  title: string
  items: NavItem[]
}

function NavSections({ sections }: { sections: NavSection[] }) {
  return (
    <>
      {sections
        .filter((section) => section.items.length > 0)
        .map((section, i) => (
          <div key={section.title} style={{ marginTop: i === 0 ? 0 : 18 }}>
            <Text fz={11} fw={700} tt="uppercase" c="dimmed" px={12} mb={6} lts={0.6}>
              {section.title}
            </Text>
            <NavLinks items={section.items} />
          </div>
        ))}
    </>
  )
}

function NavLinks({ items }: { items: NavItem[] }) {
  const location = useLocation()
  return (
    <>
      {items.map((item) => {
        const active = !!item.path && location.pathname.startsWith(item.path)
        const style = {
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '10px 12px',
          borderRadius: 8,
          textDecoration: 'none',
          fontWeight: active ? 700 : 500,
          color: active ? '#1a1625' : '#5e5873',
          background: active ? 'rgba(116,65,224,0.12)' : 'transparent',
          marginBottom: 4,
        }
        const body = (
          <>
            {item.icon}
            <Text fz="sm">{item.label}</Text>
          </>
        )
        return item.path ? (
          <NavLink key={item.label} to={item.path} style={style}>
            {body}
          </NavLink>
        ) : (
          <a key={item.label} href={item.href} style={style}>
            {body}
          </a>
        )
      })}
    </>
  )
}

export function Shell({ children }: { children: React.ReactNode }) {
  const { logout, impersonation, hasGlobalPermission } = useAdmin()
  const location = useLocation()
  // Phones: the sidebar is hidden behind a menu button and opens as a side
  // drawer over a dimmed page (a tap beside it, Esc or a link closes it).
  const [menuOpen, { toggle: toggleMenu, close: closeMenu }] = useDisclosure(false)

  useEffect(() => {
    closeMenu()
  }, [location.pathname, closeMenu])

  // Two views of one portal: what a club's own admins do, and the platform
  // itself (global permissions only).
  const sections: NavSection[] = [
    {
      title: 'My clubs',
      items: [
        { path: '/app/my-tenants', label: 'My Clubs', icon: <IconHome size={22} /> },
        { href: `${SSO_URL}/start`, label: 'Start a Club', icon: <IconPlus size={22} /> },
        { href: `${SSO_URL}/clubs`, label: 'Find a Club', icon: <IconSearch size={22} /> },
      ],
    },
    {
      title: 'Platform',
      items: [
        ...(hasGlobalPermission('tenants.read')
          ? [{ path: '/app/tenants', label: 'All Clubs', icon: <IconBuildingCog size={22} /> }]
          : []),
        ...(hasGlobalPermission('requests.read.all')
          ? [
              {
                path: '/app/requests',
                label: 'Club Requests',
                icon: <IconClipboardList size={22} />,
              },
            ]
          : []),
        ...(hasGlobalPermission('platform.settings')
          ? [
              {
                path: '/app/platform/settings',
                label: 'Platform Settings',
                icon: <IconSettings size={22} />,
              },
            ]
          : []),
        ...(hasGlobalPermission('plugins.manage')
          ? [{ path: '/app/plugins', label: 'Plugins', icon: <IconPuzzle size={22} /> }]
          : []),
        ...(hasGlobalPermission('roles.manage')
          ? [{ path: '/app/roles', label: 'Roles', icon: <IconKey size={22} /> }]
          : []),
        ...(hasGlobalPermission('audit.read')
          ? [{ path: '/app/audit', label: 'Audit Log', icon: <IconShieldCheck size={22} /> }]
          : []),
      ],
    },
  ]

  const logoutButton = (
    <UnstyledButton
      onClick={logout}
      style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#5e5873' }}
    >
      <IconLogout size={18} />
      <Text fz="sm">Logout</Text>
    </UnstyledButton>
  )

  return (
    <AppShell
      // The header is for phones only; from sm up the sidebar has the brand.
      header={{ height: { base: 56, sm: 0 } }}
      navbar={{
        width: 220,
        breakpoint: 'sm',
        collapsed: { mobile: true },
      }}
      padding={{ base: 'md', sm: 'xl' }}
    >
      <AppShell.Header hiddenFrom="sm" px="md" style={{ display: 'flex', alignItems: 'center' }}>
        <Group gap={12} wrap="nowrap">
          <Burger
            opened={menuOpen}
            onClick={toggleMenu}
            size="sm"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          />
          <div className="logo-mark" />
          <Text fz={20} className="wordmark">
            hubra
          </Text>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md" style={{ background: '#fff' }}>
        <Group mb={30} px="sm">
          <Brand />
        </Group>
        <NavSections sections={sections} />
        <Group mt="auto" px="sm" style={{ marginTop: 'auto' }}>
          {logoutButton}
        </Group>
      </AppShell.Navbar>

      <Drawer
        opened={menuOpen}
        onClose={closeMenu}
        size="min(280px, 85vw)"
        padding="md"
        hiddenFrom="sm"
        title={<Brand />}
      >
        <Stack gap={0}>
          <NavSections sections={sections} />
          <Group mt="lg" px="sm">
            {logoutButton}
          </Group>
        </Stack>
      </Drawer>

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
