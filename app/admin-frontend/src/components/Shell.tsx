import { useEffect, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  ActionIcon,
  AppShell,
  Badge,
  Box,
  Button,
  Drawer,
  Group,
  Menu,
  ScrollArea,
  Stack,
  Text,
  UnstyledButton,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { useQuery } from '@tanstack/react-query'
import { SSO_URL } from '@hubra/api-client'
import {
  IconArrowUpRight,
  IconBuildingCommunity,
  IconCheck,
  IconChevronRight,
  IconClipboardList,
  IconDatabase,
  IconDotsVertical,
  IconHeartbeat,
  IconHome,
  IconKey,
  IconLayoutSidebarLeftCollapse,
  IconLogout,
  IconMenu2,
  IconPuzzle,
  IconSettings,
  IconShieldCheck,
  IconUserCircle,
  IconWorld,
} from '@tabler/icons-react'
import { useAdmin } from '@/context/AdminContext'
import { getProfile } from '@/api/auth'
import { ThemeSwitch } from '@hubra/ui'
import { useLang, type Lang } from '@/lang'

// The same frame as the club app (components/Shell there): a white top bar
// with logo, breadcrumb, language and account, a collapsible sidebar with
// section labels and a user card at its foot.

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

const COLLAPSED_KEY = 'hubra_manage_sidebar_collapsed'

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSED_KEY) === '1'
  } catch {
    return false
  }
}

function initials(name: string) {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((p) => p[0]?.toUpperCase())
      .join('') || '?'
  )
}

function contrastColor(hex: string) {
  const h = hex.replace('#', '')
  if (h.length !== 6) return '#1a1625'
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16))
  return r * 0.299 + g * 0.587 + b * 0.114 > 160 ? '#1a1625' : '#ffffff'
}

function NavRow({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  const location = useLocation()
  const active = !!item.path && location.pathname.startsWith(item.path)
  const style: React.CSSProperties = collapsed
    ? {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 44,
        height: 44,
        borderRadius: 10,
        color: active ? 'var(--mantine-color-acc-8)' : 'var(--hb-text-2)',
        background: active ? 'var(--mantine-color-acc-1)' : 'transparent',
      }
    : {
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        minHeight: 40,
        padding: '8px 12px',
        borderRadius: 10,
        textDecoration: 'none',
        fontSize: 'var(--mantine-font-size-sm)',
        fontWeight: active ? 700 : 500,
        color: active ? 'var(--mantine-color-acc-8)' : 'var(--hb-text-2)',
        background: active ? 'var(--mantine-color-acc-1)' : 'transparent',
        transition: 'background .15s, color .15s',
      }
  const body = collapsed ? (
    item.icon
  ) : (
    <>
      <Box component="span" style={{ display: 'flex', color: active ? 'var(--mantine-color-acc-6)' : 'var(--hb-text-2)' }}>
        {item.icon}
      </Box>
      <span style={{ flex: 1 }}>{item.label}</span>
      {item.href && <IconArrowUpRight size={14} color="var(--hb-text-3)" />}
    </>
  )
  return item.path ? (
    <NavLink
      to={item.path}
      style={style}
      className="manage-nav-row"
      title={collapsed ? item.label : undefined}
      aria-current={active ? 'page' : undefined}
    >
      {body}
    </NavLink>
  ) : (
    <a
      href={item.href}
      style={style}
      className="manage-nav-row"
      title={collapsed ? item.label : undefined}
    >
      {body}
    </a>
  )
}

function NavSections({ sections, collapsed = false }: { sections: NavSection[]; collapsed?: boolean }) {
  return (
    <Stack gap={collapsed ? 12 : 20}>
      {sections.map((section) => (
        <Stack key={section.label} gap={collapsed ? 8 : 2} align={collapsed ? 'center' : undefined}>
          {!collapsed && (
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
          )}
          {section.items.map((item) => (
            <NavRow key={item.label} item={item} collapsed={collapsed} />
          ))}
        </Stack>
      ))}
    </Stack>
  )
}

function LanguageMenu() {
  const { lang, setLang } = useLang()
  const labels: Record<Lang, string> = { de: 'Deutsch', en: 'English' }
  return (
    <Menu shadow="md" width={160} position="bottom-end">
      <Menu.Target>
        <Button
          variant="subtle"
          color="gray"
          size="sm"
          px={10}
          leftSection={<IconWorld size={17} />}
          aria-label={labels[lang]}
        >
          {lang.toUpperCase()}
        </Button>
      </Menu.Target>
      <Menu.Dropdown>
        {(['de', 'en'] as Lang[]).map((l) => (
          <Menu.Item
            key={l}
            onClick={() => setLang(l)}
            rightSection={l === lang ? <IconCheck size={14} /> : null}
          >
            {labels[l]}
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  )
}

function useProfile() {
  return useQuery({ queryKey: ['profile'], queryFn: ({ signal }) => getProfile(signal) })
}

/** Name and role at the foot of the sidebar; opens the account menu. */
function UserCard() {
  const { logout, isSuperadmin } = useAdmin()
  const { lang, setLang, tr } = useLang()
  const { data: profile } = useProfile()
  const name = profile?.name ?? ''
  const bg = profile?.avatarColor ?? '#ebe8f2'
  return (
    <Menu shadow="md" width={220} position="top-start">
      <Menu.Target>
        <UnstyledButton
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            height: 52,
            padding: '0 10px',
            borderRadius: 12,
            border: '1px solid var(--hb-border)',
            background: 'var(--hb-surface)',
          }}
        >
          <Box
            style={{
              width: 34,
              height: 34,
              borderRadius: '50%',
              background: bg,
              color: contrastColor(bg),
              fontSize: 'var(--mantine-font-size-xs)',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            {initials(name)}
          </Box>
          <Box style={{ flex: 1, minWidth: 0, textAlign: 'left' }}>
            <Text fz="sm" fw={600} lh={1.2} truncate>
              {name || '…'}
            </Text>
            <Text fz="xs" c="dimmed" truncate>
              {isSuperadmin ? tr('Plattform-Admin', 'Platform admin') : tr('Vereins-Admin', 'Club admin')}
            </Text>
          </Box>
          <IconDotsVertical size={16} color="var(--mantine-color-dimmed)" />
        </UnstyledButton>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Item component="a" href={`${SSO_URL}/account`} leftSection={<IconUserCircle size={16} />}>
          {tr('Mein Konto', 'My account')}
        </Menu.Item>
        <Menu.Item
          leftSection={<IconWorld size={16} />}
          onClick={() => setLang(lang === 'de' ? 'en' : 'de')}
        >
          {lang === 'de' ? 'English' : 'Deutsch'}
        </Menu.Item>
        <Group justify="space-between" px={12} py={6} wrap="nowrap">
          <Text fz="sm">{tr('Darstellung', 'Appearance')}</Text>
          <ThemeSwitch
            labels={{
              light: tr('Hell', 'Light'),
              dark: tr('Dunkel', 'Dark'),
              system: tr('Wie Gerät', 'Like device'),
            }}
          />
        </Group>
        <Menu.Divider />
        <Menu.Item color="red" leftSection={<IconLogout size={16} />} onClick={logout}>
          {tr('Abmelden', 'Sign out')}
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  )
}

export function Shell({ children }: { children: React.ReactNode }) {
  const { impersonation, hasGlobalPermission, logout } = useAdmin()
  const { tr } = useLang()
  const location = useLocation()
  const { data: profile } = useProfile()
  // Phones: the sidebar is hidden behind a menu button and opens as a side
  // drawer over a dimmed page (a tap beside it, Esc or a link closes it).
  const [menuOpen, { open: openMenu, close: closeMenu }] = useDisclosure(false)
  const [collapsed, setCollapsed] = useState(readCollapsed)

  useEffect(() => {
    closeMenu()
  }, [location.pathname, closeMenu])

  const toggleCollapsed = () => {
    setCollapsed((c) => {
      try {
        localStorage.setItem(COLLAPSED_KEY, c ? '0' : '1')
      } catch {
        /* private mode: keep it for this visit */
      }
      return !c
    })
  }

  const platformItems: NavItem[] = [
    ...(hasGlobalPermission('tenants.read')
      ? [{ path: '/app/tenants', label: tr('Alle Vereine', 'All clubs'), icon: <IconBuildingCommunity size={24} /> }]
      : []),
    ...(hasGlobalPermission('requests.read.all')
      ? [{ path: '/app/requests', label: tr('Vereinsanfragen', 'Club requests'), icon: <IconClipboardList size={24} /> }]
      : []),
    ...(hasGlobalPermission('platform.settings')
      ? [{ path: '/app/platform/settings', label: tr('Einstellungen', 'Settings'), icon: <IconSettings size={24} /> }]
      : []),
    ...(hasGlobalPermission('backups.manage')
      ? [{ path: '/app/platform/backups', label: tr('Backups', 'Backups'), icon: <IconDatabase size={24} /> }]
      : []),
    ...(hasGlobalPermission('platform.diagnostics')
      ? [{ path: '/app/platform/diagnostics', label: tr('Diagnose', 'Diagnostics'), icon: <IconHeartbeat size={24} /> }]
      : []),
    ...(hasGlobalPermission('plugins.manage')
      ? [{ path: '/app/plugins', label: tr('Plugin-Katalog', 'Plugin catalogue'), icon: <IconPuzzle size={24} /> }]
      : []),
    ...(hasGlobalPermission('roles.manage')
      ? [{ path: '/app/roles', label: tr('Rollen', 'Roles'), icon: <IconKey size={24} /> }]
      : []),
    ...(hasGlobalPermission('audit.read')
      ? [{ path: '/app/audit', label: tr('Audit-Log', 'Audit log'), icon: <IconShieldCheck size={24} /> }]
      : []),
  ]

  const sections: NavSection[] = [
    {
      label: tr('Persönlich', 'Personal'),
      items: [
        // Joining and founding clubs live on the sign-in site («Meine Vereine»);
        // here are only the clubs this person runs.
        { path: '/app/my-tenants', label: tr('Deine Vereine verwalten', 'Clubs you run'), icon: <IconHome size={24} /> },
      ],
    },
    ...(platformItems.length > 0
      ? [{ label: tr('Plattform', 'Platform'), items: platformItems }]
      : []),
  ]

  // Breadcrumb: "Verwaltung › <page>", like the club app's top bar.
  const current = sections
    .flatMap((s) => s.items)
    .filter((i) => i.path && location.pathname.startsWith(i.path))
    .sort((a, b) => (b.path?.length ?? 0) - (a.path?.length ?? 0))[0]
  const crumbs = [tr('Verwaltung', 'Manage'), ...(current ? [current.label] : [])]

  return (
    <AppShell
      header={{ height: 64 }}
      navbar={{
        width: { base: 244, sm: collapsed ? 64 : 244 },
        breakpoint: 'sm',
        collapsed: { mobile: true, desktop: false },
      }}
      padding={0}
      styles={{ main: { background: 'var(--hb-page)' } }}
    >
      <AppShell.Header>
        <Group
          h={64}
          gap="xs"
          px="md"
          wrap="nowrap"
          style={{ background: 'var(--hb-surface)', borderBottom: '1px solid var(--hb-border)' }}
        >
          <ActionIcon
            variant="subtle"
            size="lg"
            hiddenFrom="sm"
            onClick={openMenu}
            aria-label={tr('Menü öffnen', 'Open menu')}
          >
            <IconMenu2 size={20} />
          </ActionIcon>
          <Group gap={8} wrap="nowrap" style={{ flexShrink: 0 }}>
            <div className="logo-mark" />
            <Text fz={22} className="wordmark" visibleFrom="xs">
              hubra
            </Text>
          </Group>
          <ActionIcon
            variant="subtle"
            size="lg"
            visibleFrom="sm"
            onClick={toggleCollapsed}
            aria-label={tr('Seitenleiste ein- oder ausblenden', 'Toggle sidebar')}
          >
            <IconLayoutSidebarLeftCollapse size={20} />
          </ActionIcon>
          <Group gap={4} flex={1} wrap="nowrap" style={{ minWidth: 0, overflow: 'hidden' }}>
            {crumbs.map((c, i) => (
              <Group key={c + i} gap={4} wrap="nowrap" style={{ minWidth: 0 }}>
                {i > 0 && <IconChevronRight size={14} color="var(--mantine-color-dimmed)" style={{ flexShrink: 0 }} />}
                <Text
                  fz="sm"
                  c={i === crumbs.length - 1 ? 'dark' : 'dimmed'}
                  fw={i === crumbs.length - 1 ? 600 : 400}
                  truncate
                >
                  {c}
                </Text>
              </Group>
            ))}
          </Group>
          <Box visibleFrom="sm">
            <LanguageMenu />
          </Box>
          <ActionIcon variant="subtle" size="lg" onClick={logout} aria-label={tr('Abmelden', 'Sign out')}>
            <IconLogout size={18} />
          </ActionIcon>
          {/* The expanded sidebar already shows the user card; the avatar
              here only stands in for it while the sidebar is collapsed. */}
          {collapsed && (
            <Box
              visibleFrom="sm"
              style={{
                width: 34,
                height: 34,
                borderRadius: '50%',
                background: profile?.avatarColor ?? '#ebe8f2',
                color: contrastColor(profile?.avatarColor ?? '#ebe8f2'),
                fontSize: 'var(--mantine-font-size-xs)',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
              title={profile?.name}
            >
              {initials(profile?.name ?? '')}
            </Box>
          )}
        </Group>
      </AppShell.Header>

      <AppShell.Navbar style={{ background: 'var(--hb-surface)' }}>
        <ScrollArea flex={1} type="auto" offsetScrollbars>
          <Box p={collapsed ? 10 : 'sm'} pt="md">
            <NavSections sections={sections} collapsed={collapsed} />
          </Box>
        </ScrollArea>
        {!collapsed && (
          <Box p="xs" style={{ borderTop: '1px solid var(--hb-border)' }}>
            <UserCard />
          </Box>
        )}
      </AppShell.Navbar>

      <Drawer
        opened={menuOpen}
        onClose={closeMenu}
        position="left"
        size="min(300px, 85vw)"
        padding="md"
        hiddenFrom="sm"
        title={
          <Group gap={8} wrap="nowrap">
            <div className="logo-mark" />
            <Text fz={20} className="wordmark">
              hubra
            </Text>
          </Group>
        }
        styles={{ body: { display: 'flex', flexDirection: 'column', minHeight: 'calc(100% - 72px)' } }}
      >
        <Box style={{ flex: 1 }}>
          <NavSections sections={sections} />
        </Box>
        <Box mt="xl">
          <UserCard />
        </Box>
      </Drawer>

      <AppShell.Main>
        {impersonation?.is_impersonating && (
          <Group
            gap={10}
            px="md"
            py={8}
            wrap="wrap"
            style={{ background: 'var(--mantine-color-gold-light)', borderBottom: '1px solid var(--mantine-color-gold-4)' }}
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
