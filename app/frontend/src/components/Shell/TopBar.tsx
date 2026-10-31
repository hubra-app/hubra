import {
  Group,
  ActionIcon,
  Text,
  Indicator,
  Box,
  UnstyledButton,
} from '@mantine/core'
import {
  IconMenu2,
  IconLayoutSidebarLeftCollapse,
  IconChevronRight,
  IconBell,
  IconSearch,
  IconX,
} from '@tabler/icons-react'
import { useState } from 'react'
import { useT } from '@/locales/i18n'
import { useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useNav, useAuth } from '@/context/AppContext'
import { listNotifications } from '@/api/notifications'
import { LanguageSwitcher } from '@/components/LanguageSwitcher'
import { GlobalSearch } from './GlobalSearch'
import { UserMenu } from './UserMenu'
import { WhatsNewModal } from './WhatsNew'
import { getBreadcrumb, initials, contrastColor } from './nav'
import { qk } from '@/data/keys'
import { useClubColors } from '@/branding'
import { ClubMark } from './ClubMark'

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
  const { currentUser } = useAuth()
  const crumb = getBreadcrumb(location.pathname, t)
  const parts = crumb.split(' > ')

  // The panel polls the same query; the server counts all unread ones,
  // not just the newest 100 the list holds.
  const { data: notifications } = useQuery({
    queryKey: qk.notifications,
    queryFn: listNotifications,
    refetchInterval: 30_000,
  })
  const unreadCount = notifications?.unread ?? 0

  const { secondary } = useClubColors()

  // Phones: the search takes over the bar while it is open.
  const [mobileSearch, setMobileSearch] = useState(false)
  const barStyle = {
    background: 'var(--hb-surface)',
    borderBottom: secondary
      ? '3px solid var(--mantine-color-club2-6)'
      : '1px solid var(--hb-border)',
    flexWrap: 'nowrap' as const,
  }

  if (mobileSearch) {
    return (
      <Group h={64} gap="xs" px="md" style={barStyle} wrap="nowrap">
        <GlobalSearch fullWidth onDone={() => setMobileSearch(false)} />
        <ActionIcon
          variant="subtle"
          size="lg"
          onClick={() => setMobileSearch(false)}
          aria-label={t('common.close', 'Schliessen')}
        >
          <IconX size={20} />
        </ActionIcon>
      </Group>
    )
  }

  return (
    <>
    <WhatsNewModal />
    <Group
      h={64}
      gap="xs"
      px="md"
      style={barStyle}
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

      <ClubMark nameFrom="xs" />

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
      <ActionIcon
        variant="subtle"
        size="lg"
        className="mantine-hidden-from-sm"
        onClick={() => setMobileSearch(true)}
        aria-label={t('shell.search.open', 'Suchen')}
      >
        <IconSearch size={18} />
      </ActionIcon>
      <div className="mantine-visible-from-sm">
        <LanguageSwitcher />
      </div>

      <Group gap={4} style={{ flexShrink: 0 }} wrap="nowrap">

        <ActionIcon
          variant="subtle"
          size="lg"
          aria-label={
            unreadCount > 0
              ? t('shell.a11y.notificationsUnread', 'Benachrichtigungen, {{count}} ungelesen', {
                  count: unreadCount,
                })
              : t('shell.a11y.notifications', 'Benachrichtigungen')
          }
          onClick={() => setNotifPanelOpen(!notifPanelOpen)}
        >
          <Indicator
            disabled={unreadCount === 0}
            label={unreadCount > 99 ? '99+' : unreadCount}
            color="red"
            size={16}
            offset={2}
            withBorder
            styles={{ indicator: { fontSize: 10, fontWeight: 700, padding: '0 4px' } }}
          >
            <IconBell size={20} style={{ display: 'block' }} />
          </Indicator>
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
    </>
  )
}
