import { useEffect } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  AppShell,
  Badge,
  Box,
  Burger,
  Button,
  Drawer,
  Group,
  SegmentedControl,
  Stack,
  Text,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { SSO_URL } from '@hubra/api-client'
import {
  IconArrowUpRight,
  IconBuildingCommunity,
  IconClipboardList,
  IconHome,
  IconKey,
  IconLogout,
  IconPuzzle,
  IconSearch,
  IconShieldCheck,
} from '@tabler/icons-react'
import { useAdmin } from '@/context/AdminContext'
import { useLang, type Lang } from '@/lang'

interface NavItem {
  label: string
  icon: React.ReactNode
  /** In-app route… */
  path?: string
  /** …or a page of another Hubra app. */
  href?: string
}

interface NavSection {
  label: string
  items: NavItem[]
}

function Brand() {
  const { tr } = useLang()
  return (
    <Group gap={10} wrap="nowrap">
      <div className="logo-mark" />
      <div>
        <Text fz={20} className="wordmark">
          hubra
        </Text>
        <Text fz={11} fw={600} c="dimmed" tt="uppercase" style={{ letterSpacing: '0.08em' }}>
          {tr('Verwaltung', 'Manage')}
        </Text>
      </div>
    </Group>
  )
}

function NavRow({ item }: { item: NavItem }) {
  const location = useLocation()
  const active = !!item.path && location.pathname.startsWith(item.path)
  const style: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    minHeight: 40,
    padding: '8px 12px',
    borderRadius: 10,
    textDecoration: 'none',
    fontSize: 'var(--mantine-font-size-sm)',
    fontWeight: active ? 700 : 500,
    color: active ? '#4d27a0' : '#4a4560',
    background: active ? '#ebe3ff' : 'transparent',
  }
  const body = (
    <>
      <Box component="span" style={{ display: 'flex', color: active ? '#7441e0' : '#5e5873' }}>
        {item.icon}
      </Box>
      <span style={{ flex: 1 }}>{item.label}</span>
      {item.href && <IconArrowUpRight size={14} color="#b7b0c9" />}
    </>
  )
  return item.path ? (
    <NavLink
      to={item.path}
      style={style}
      className="manage-nav-row"
      aria-current={active ? 'page' : undefined}
    >
      {body}
    </NavLink>
  ) : (
    <a href={item.href} style={style} className="manage-nav-row">
      {body}
    </a>
  )
}

function NavSections({ sections }: { sections: NavSection[] }) {
  return (
    <Stack gap={20}>
      {sections.map((section) => (
        <Stack key={section.label} gap={2}>
          <Text
            fz={11}
            fw={700}
            c="gray.6"
            tt="uppercase"
            px={12}
            mb={4}
            style={{ letterSpacing: '0.08em' }}
          >
            {section.label}
          </Text>
          {section.items.map((item) => (
            <NavRow key={item.label} item={item} />
          ))}
        </Stack>
      ))}
    </Stack>
  )
}

function SidebarFooter() {
  const { logout } = useAdmin()
  const { lang, setLang, tr } = useLang()
  return (
    <Stack gap={10} pt="md" style={{ borderTop: '1px solid #ebe8f2' }}>
      <SegmentedControl
        size="xs"
        radius="md"
        value={lang}
        onChange={(v) => setLang(v as Lang)}
        data={[
          { value: 'de', label: 'Deutsch' },
          { value: 'en', label: 'English' },
        ]}
        aria-label={tr('Sprache', 'Language')}
      />
      <Button
        variant="subtle"
        color="gray"
        justify="flex-start"
        leftSection={<IconLogout size={18} />}
        onClick={logout}
      >
        {tr('Abmelden', 'Sign out')}
      </Button>
    </Stack>
  )
}

export function Shell({ children }: { children: React.ReactNode }) {
  const { impersonation, hasGlobalPermission } = useAdmin()
  const { tr } = useLang()
  const location = useLocation()
  // Phones: the sidebar is hidden behind a menu button and opens as a side
  // drawer over a dimmed page (a tap beside it, Esc or a link closes it).
  const [menuOpen, { toggle: toggleMenu, close: closeMenu }] = useDisclosure(false)

  useEffect(() => {
    closeMenu()
  }, [location.pathname, closeMenu])

  const platformItems: NavItem[] = [
    ...(hasGlobalPermission('tenants.read')
      ? [{ path: '/app/tenants', label: tr('Alle Vereine', 'All clubs'), icon: <IconBuildingCommunity size={20} /> }]
      : []),
    ...(hasGlobalPermission('plugins.manage')
      ? [{ path: '/app/plugins', label: tr('Plugins', 'Plugins'), icon: <IconPuzzle size={20} /> }]
      : []),
    ...(hasGlobalPermission('roles.manage')
      ? [{ path: '/app/roles', label: tr('Rollen', 'Roles'), icon: <IconKey size={20} /> }]
      : []),
    ...(hasGlobalPermission('audit.read')
      ? [{ path: '/app/audit', label: tr('Audit-Log', 'Audit log'), icon: <IconShieldCheck size={20} /> }]
      : []),
  ]

  const sections: NavSection[] = [
    {
      label: tr('Persönlich', 'Personal'),
      items: [
        { path: '/app/my-tenants', label: tr('Meine Vereine', 'My clubs'), icon: <IconHome size={20} /> },
        { path: '/app/requests', label: tr('Meine Anfragen', 'My requests'), icon: <IconClipboardList size={20} /> },
        { href: `${SSO_URL}/clubs`, label: tr('Verein finden', 'Find a club'), icon: <IconSearch size={20} /> },
      ],
    },
    ...(platformItems.length > 0
      ? [{ label: tr('Plattform', 'Platform'), items: platformItems }]
      : []),
  ]

  return (
    <AppShell
      // The header is for phones only; from sm up the sidebar has the brand.
      header={{ height: { base: 56, sm: 0 } }}
      navbar={{
        width: 248,
        breakpoint: 'sm',
        collapsed: { mobile: true },
      }}
      padding={0}
    >
      <AppShell.Header hiddenFrom="sm" px="md" style={{ display: 'flex', alignItems: 'center' }}>
        <Group gap={12} wrap="nowrap">
          <Burger
            opened={menuOpen}
            onClick={toggleMenu}
            size="sm"
            aria-label={menuOpen ? tr('Menü schliessen', 'Close menu') : tr('Menü öffnen', 'Open menu')}
          />
          <div className="logo-mark" />
          <Text fz={20} className="wordmark">
            hubra
          </Text>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md" style={{ background: '#fff', borderRight: '1px solid #ebe8f2' }}>
        <Box px={12} pt={6} mb={28}>
          <Brand />
        </Box>
        <AppShell.Section grow style={{ overflowY: 'auto' }}>
          <NavSections sections={sections} />
        </AppShell.Section>
        <AppShell.Section>
          <SidebarFooter />
        </AppShell.Section>
      </AppShell.Navbar>

      <Drawer
        opened={menuOpen}
        onClose={closeMenu}
        position="left"
        size="min(300px, 85vw)"
        padding="md"
        hiddenFrom="sm"
        title={<Brand />}
        styles={{ body: { display: 'flex', flexDirection: 'column', minHeight: 'calc(100% - 72px)' } }}
      >
        <Box style={{ flex: 1 }}>
          <NavSections sections={sections} />
        </Box>
        <Box mt="xl">
          <SidebarFooter />
        </Box>
      </Drawer>

      <AppShell.Main style={{ background: '#f7f6fb' }}>
        {impersonation?.is_impersonating && (
          <Group
            gap={10}
            px="md"
            py={8}
            wrap="wrap"
            style={{ background: '#fffbeb', borderBottom: '1px solid #fce588' }}
          >
            <Badge color="gold" c="#1a1625" variant="filled" size="sm">
              {tr('Stellvertretung', 'Impersonating')}
            </Badge>
            <Text fz="sm" fw={600}>
              {tr('Aktiv im Verein', 'Acting in club')}: {impersonation.tenant_slug}
            </Text>
            {impersonation.reason && (
              <Text fz="xs" c="dimmed">
                {tr('Grund', 'Reason')}: {impersonation.reason}
              </Text>
            )}
          </Group>
        )}
        <div className="page-container">{children}</div>
      </AppShell.Main>
    </AppShell>
  )
}
