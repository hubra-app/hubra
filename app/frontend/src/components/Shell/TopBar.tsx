import {
  Group,
  ActionIcon,
  Text,
  Badge,
  Box,
  HoverCard,
  Stack,
  UnstyledButton,
} from '@mantine/core'
import {
  IconMenu2,
  IconLayoutSidebarLeftCollapse,
  IconChevronRight,
  IconBell,
  IconLogout,
  IconBolt,
} from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useNav, useAuth } from '@/context/AppContext'
import { getChangelog } from '@/api/system'
import { listNotifications } from '@/api/notifications'
import { LanguageSwitcher } from '@/components/LanguageSwitcher'
import { GlobalSearch } from './GlobalSearch'
import { UserMenu } from './UserMenu'
import { getBreadcrumb, initials, contrastColor } from './nav'
import { qk } from '@/data/keys'
import { useClubColors } from '@/branding'
import { useClubProfile } from '@/data/clubProfile'

export function TopBar() {
  const { t } = useT()
  const location = useLocation()
  const {
    sidebarCollapsed,
    setSidebarCollapsed,
    setMobileDrawerOpen,
    notifPanelOpen,
    setNotifPanelOpen,
    userMenuOpen,
    setUserMenuOpen,
  } = useNav()
  const { setPhase, currentUser } = useAuth()
  const crumb = getBreadcrumb(location.pathname, t)
  const parts = crumb.split(' > ')

  const { data: changelog } = useQuery({
    queryKey: qk.changelog,
    queryFn: getChangelog,
  })
  const latestEntries = changelog?.entries?.slice(0, 2) ?? []

  const { data: notifications = [] } = useQuery({
    queryKey: qk.notifications,
    queryFn: listNotifications,
  })
  const unreadCount = notifications.filter((n) => !n.read).length

  const { data: club } = useClubProfile()
  const { secondary } = useClubColors()

  return (
    <Group
      h={64}
      gap="xs"
      px="md"
      style={{
        background: 'var(--hb-surface)',
        borderBottom: secondary
          ? '3px solid var(--mantine-color-club2-6)'
          : '1px solid var(--hb-border)',
        flexWrap: 'nowrap',
      }}
      wrap="nowrap"
    >
      <ActionIcon
        variant="subtle"
        size="lg"
        className="mantine-hidden-from-sm"
        onClick={() => setMobileDrawerOpen(true)}
        aria-label={t('shell.a11y.menu', 'Menü')}
      >
        <IconMenu2 size={20} />
      </ActionIcon>

      {club?.logo ? (
        <Group gap={10} wrap="nowrap" style={{ flexShrink: 1, minWidth: 0, maxWidth: 280 }}>
          <img src={club.logo} alt="" className="club-logo" />
          <Text fz="lg" fw={700} truncate className="mantine-visible-from-xs">
            {club.club_name}
          </Text>
        </Group>
      ) : (
        <Group gap={8} wrap="nowrap" style={{ flexShrink: 0 }}>
          <div className="logo-mark" />
          <Text fz={22} className="wordmark mantine-visible-from-xs">
            hubra
          </Text>
        </Group>
      )}

      <ActionIcon
        variant="subtle"
        size="lg"
        className="mantine-visible-from-sm"
        onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
        aria-label={t('shell.a11y.toggleSidebar', 'Seitenleiste ein- oder ausblenden')}
      >
        <IconLayoutSidebarLeftCollapse size={20} />
      </ActionIcon>

      <Group
        gap={4}
        flex={1}
        style={{ minWidth: 0, overflow: 'hidden' }}
        wrap="nowrap"
      >
        {parts.map((p, i) => (
          <Group
            key={p + i}
            gap={4}
            wrap="nowrap"
            style={{ flexShrink: i < parts.length - 1 ? 0 : 1, minWidth: 0 }}
          >
            {i > 0 && (
              <IconChevronRight
                size={14}
                style={{ color: 'var(--mantine-color-dimmed)', flexShrink: 0 }}
              />
            )}
            <Text
              fz="sm"
              c={i === parts.length - 1 ? 'var(--hb-text)' : 'dimmed'}
              fw={i === parts.length - 1 ? 600 : 400}
              style={{ whiteSpace: 'nowrap' }}
            >
              {p}
            </Text>
          </Group>
        ))}
      </Group>

      <GlobalSearch />
      <div className="mantine-visible-from-sm">
        <LanguageSwitcher />
      </div>

      <Group gap={4} style={{ flexShrink: 0 }} wrap="nowrap">
        <HoverCard width={220} shadow="md" position="bottom-end">
          <HoverCard.Target>
            <ActionIcon
              variant="subtle"
              size="lg"
              className="mantine-visible-from-sm"
              aria-label={t('shell.whatsNew.title')}
            >
              <IconBolt size={18} />
            </ActionIcon>
          </HoverCard.Target>
          <HoverCard.Dropdown p="md">
            <Stack gap={8}>
              <Text fz="sm" fw={600}>
                {t('shell.whatsNew.title')}
              </Text>
              {latestEntries.length > 0 ? (
                latestEntries.map((entry) => (
                  <div key={entry.version}>
                    <Text fz="xs" fw={600} c="var(--hb-text)">
                      v{entry.version}
                      {entry.date && (
                        <Text component="span" fz="xs" c="dimmed" ml={6}>
                          {entry.date}
                        </Text>
                      )}
                    </Text>
                    {Object.entries(entry.sections).map(([section, items]) =>
                      items.length > 0 ? (
                        <div key={section}>
                          <Text fz="xs" fw={500} c="var(--hb-text-2)" mt={4}>
                            {section}
                          </Text>
                          {items.map((item, i) => (
                            <Text
                              key={section + '-' + i}
                              fz="xs"
                              c="var(--hb-text-2)"
                              ml={8}
                            >
                              {item}
                            </Text>
                          ))}
                        </div>
                      ) : null,
                    )}
                  </div>
                ))
              ) : (
                <Text fz="xs" c="dimmed">
                  {t('shell.whatsNew.changelogSoon')}
                </Text>
              )}
            </Stack>
          </HoverCard.Dropdown>
        </HoverCard>

        <ActionIcon
          variant="subtle"
          size="lg"
          aria-label={t('shell.a11y.notifications', 'Benachrichtigungen')}
          style={{ position: 'relative' }}
          onClick={() => setNotifPanelOpen(!notifPanelOpen)}
        >
          <IconBell size={18} />
          {unreadCount > 0 && (
            <Badge
              color="red"
              size="xs"
              circle
              pos="absolute"
              top={4}
              right={4}
              styles={{
                root: {
                  minWidth: 16,
                  height: 16,
                  padding: 0,
                  pointerEvents: 'none',
                },
              }}
            >
              {unreadCount > 9 ? '9+' : unreadCount}
            </Badge>
          )}
        </ActionIcon>

        <ActionIcon
          variant="subtle"
          size="lg"
          aria-label={t('shell.a11y.signOut', 'Abmelden')}
          onClick={() => setPhase('login')}
        >
          <IconLogout size={18} />
        </ActionIcon>

        {/* The expanded sidebar already shows the user card with this menu;
            the avatar here only stands in for it while the sidebar is collapsed. */}
        {sidebarCollapsed && (
          <Box
            className="mantine-visible-from-sm"
            style={{ position: 'relative' }}
          >
            <UnstyledButton
              onClick={() => setUserMenuOpen(!userMenuOpen)}
              aria-label={t('shell.a11y.userMenu', 'Benutzermenü')}
            >
              <Box
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: '50%',
                  background: currentUser?.avatarColor ?? '#ebe8f2',
                  fontSize: 'var(--mantine-font-size-xs)',
                  fontWeight: 700,
                  color: contrastColor(currentUser?.avatarColor ?? '#ebe8f2'),
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                {initials(currentUser?.name ?? '')}
              </Box>
            </UnstyledButton>
            {userMenuOpen && (
              <Box
                style={{
                  position: 'absolute',
                  right: 0,
                  top: '110%',
                  zIndex: 200,
                }}
              >
                <UserMenu />
              </Box>
            )}
          </Box>
        )}
      </Group>
    </Group>
  )
}
