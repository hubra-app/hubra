import { type ReactNode } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  Anchor,
  Avatar,
  Box,
  Burger,
  Button,
  Divider,
  Drawer,
  Group,
  Menu,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Text,
  UnstyledButton,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import {
  IconChevronDown,
  IconInbox,
  IconLogout,
  IconShieldLock,
  IconUserCircle,
} from '@tabler/icons-react'
import { ThemeToggle } from '@hubra/ui'
import { useAuth } from '@/auth'
import { ACCOUNT_URL, APP_URL } from '@/urls'
import { themeLabels, useLang, type Lang } from '@/lang'
import { useNavItems } from '@/lib/nav'

function LangSwitch() {
  const { lang, setLang, tr } = useLang()
  return (
    <SegmentedControl
      size="xs"
      radius="md"
      value={lang}
      onChange={(v) => setLang(v as Lang)}
      data={[
        { value: 'de', label: 'DE' },
        { value: 'en', label: 'EN' },
      ]}
      aria-label={tr('Sprache', 'Language')}
    />
  )
}

function AccountButton() {
  const { tr } = useLang()
  const { status, profile, signInUrl, signOut } = useAuth()
  if (status === 'loading') return null
  if (status !== 'authed' || !profile) {
    return (
      <Button size="xs" variant="light" component="a" href={signInUrl()}>
        {tr('Anmelden', 'Sign in')}
      </Button>
    )
  }
  return (
    <Menu position="bottom-end" width={240} withinPortal>
      <Menu.Target>
        <UnstyledButton aria-label={tr('Konto', 'Account')} className="sp-account">
          <Group gap={6} wrap="nowrap">
            <Avatar size={28} radius="xl" color={profile.avatarColor ?? 'acc'} name={profile.name} />
            <IconChevronDown size={14} />
          </Group>
        </UnstyledButton>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>
          <Text size="sm" fw={600} c="var(--hb-text)" truncate>
            {profile.name}
          </Text>
          <Text size="xs" c="dimmed" truncate>
            {profile.email}
          </Text>
        </Menu.Label>
        <Menu.Item component={Link} to="/meine" leftSection={<IconInbox size={16} />}>
          {tr('Meine Meldungen', 'My reports')}
        </Menu.Item>
        <Menu.Item component={Link} to="/datenschutz" leftSection={<IconShieldLock size={16} />}>
          {tr('Meine Daten', 'My data')}
        </Menu.Item>
        <Menu.Item component="a" href={ACCOUNT_URL} leftSection={<IconUserCircle size={16} />}>
          {tr('Mein Konto', 'My account')}
        </Menu.Item>
        <Menu.Divider />
        <Menu.Item leftSection={<IconLogout size={16} />} onClick={signOut}>
          {tr('Abmelden', 'Sign out')}
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  )
}

function Footer() {
  const { tr } = useLang()
  const cols: { title: string; links: { to: string; label: string; external?: boolean }[] }[] = [
    {
      title: tr('Hilfe', 'Help'),
      links: [
        { to: '/hilfe', label: tr('Anleitungen', 'Guides') },
        { to: '/start', label: tr('Verein einrichten', 'Set up a club') },
        { to: '/kontakt', label: tr('Kontakt', 'Contact') },
      ],
    },
    {
      title: tr('Mitreden', 'Have a say'),
      links: [
        { to: '/roadmap', label: 'Roadmap' },
        { to: '/idee', label: tr('Idee vorschlagen', 'Suggest an idea') },
        { to: '/melden', label: tr('Problem melden', 'Report a problem') },
      ],
    },
    {
      title: tr('Vertrauen', 'Trust'),
      links: [
        { to: '/status', label: tr('Systemstatus', 'System status') },
        { to: '/sicherheit', label: tr('Sicherheit', 'Security') },
        { to: '/datenschutz', label: tr('Meine Daten', 'My data') },
      ],
    },
    {
      title: 'Hubra',
      links: [
        { to: 'https://hubra.club', label: 'hubra.club', external: true },
        { to: APP_URL, label: tr('Vereins-App', 'Club app'), external: true },
        { to: 'https://plugins.hubra.club', label: 'Plugins', external: true },
      ],
    },
  ]
  return (
    <Box component="footer" className="sp-footer">
      <Box className="sp-wrap">
        <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="lg">
          {cols.map((c) => (
            <Stack key={c.title} gap={6}>
              <Text size="xs" fw={700} tt="uppercase" c="dimmed" style={{ letterSpacing: '0.04em' }}>
                {c.title}
              </Text>
              {c.links.map((l) =>
                l.external ? (
                  <Anchor key={l.to} href={l.to} size="sm" c="var(--hb-text-2)">
                    {l.label}
                  </Anchor>
                ) : (
                  <Anchor key={l.to} component={Link} to={l.to} size="sm" c="var(--hb-text-2)">
                    {l.label}
                  </Anchor>
                ),
              )}
            </Stack>
          ))}
        </SimpleGrid>
        <Divider my="lg" />
        <Text size="xs" c="dimmed">
          © {new Date().getFullYear()} Hubra ·{' '}
          <Anchor href="https://hubra.club/impressum" size="xs" c="dimmed">
            {tr('Impressum', 'Imprint')}
          </Anchor>{' '}
          ·{' '}
          <Anchor href="https://hubra.club/datenschutz" size="xs" c="dimmed">
            {tr('Datenschutzerklärung', 'Privacy policy')}
          </Anchor>
        </Text>
      </Box>
    </Box>
  )
}

export function Layout() {
  const { tr } = useLang()
  const items = useNavItems()
  const [open, { toggle, close }] = useDisclosure(false)
  const location = useLocation()
  return (
    <div className="sp-page">
      <header className="sp-topbar">
        <Group justify="space-between" wrap="nowrap" className="sp-wrap" h="100%">
          <Group gap={28} wrap="nowrap">
            <Link to="/" className="sp-brand" aria-label={tr('Hubra Support, Startseite', 'Hubra Support, home')}>
              <div className="logo-mark" />
              <Text fz={20} className="wordmark">
                hubra
              </Text>
              <Text fz={13} fw={700} className="sp-brand-tag">
                Support
              </Text>
            </Link>
            <Group gap={2} wrap="nowrap" visibleFrom="md" component="nav">
              {items.map((i) => (
                <NavLink key={i.to} to={i.to} className="sp-nav">
                  {i.label}
                </NavLink>
              ))}
            </Group>
          </Group>
          <Group gap={6} wrap="nowrap">
            <Group gap={4} wrap="nowrap" visibleFrom="sm">
              <ThemeToggle labels={themeLabels(tr)} />
              <LangSwitch />
            </Group>
            <AccountButton />
            <Burger
              hiddenFrom="md"
              opened={open}
              onClick={toggle}
              size="sm"
              aria-label={tr('Menü', 'Menu')}
            />
          </Group>
        </Group>
      </header>
      <Drawer
        opened={open}
        onClose={close}
        position="right"
        size="100%"
        title={tr('Menü', 'Menu')}
        hiddenFrom="md"
        key={location.pathname}
      >
        <Stack gap={4}>
          {items.map((i) => (
            <NavLink key={i.to} to={i.to} className="sp-nav sp-nav-block" onClick={close}>
              {i.label}
            </NavLink>
          ))}
          <Divider my="sm" />
          <NavLink to="/melden" className="sp-nav sp-nav-block" onClick={close}>
            {tr('Problem melden', 'Report a problem')}
          </NavLink>
          <NavLink to="/idee" className="sp-nav sp-nav-block" onClick={close}>
            {tr('Idee vorschlagen', 'Suggest an idea')}
          </NavLink>
          <NavLink to="/meine" className="sp-nav sp-nav-block" onClick={close}>
            {tr('Meine Meldungen', 'My reports')}
          </NavLink>
          <Divider my="sm" />
          <Group gap={6}>
            <ThemeToggle labels={themeLabels(tr)} />
            <LangSwitch />
          </Group>
        </Stack>
      </Drawer>
      <main className="sp-main">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}

/** The width and spacing every page shares. */
export function Page({
  title,
  intro,
  children,
  narrow = false,
  actions,
}: {
  title: ReactNode
  intro?: ReactNode
  children: ReactNode
  narrow?: boolean
  actions?: ReactNode
}) {
  return (
    <Box className="sp-wrap" py={{ base: 24, sm: 40 }} style={narrow ? { maxWidth: 760 } : undefined}>
      <Group justify="space-between" align="flex-start" gap="md" mb={intro ? 6 : 24}>
        <Text component="h1" className="sp-h1">
          {title}
        </Text>
        {actions}
      </Group>
      {intro && (
        <Text c="dimmed" mb={28} maw={720}>
          {intro}
        </Text>
      )}
      {children}
    </Box>
  )
}
