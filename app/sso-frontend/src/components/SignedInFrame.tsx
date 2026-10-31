import type { ReactNode } from 'react'
import { ActionIcon, Box, Button, Group, Indicator, Text } from '@mantine/core'
import { useQuery } from '@tanstack/react-query'
import { IconBell, IconBuildingCommunity, IconLogout, IconUserCircle } from '@tabler/icons-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { clearTokens } from '@hubra/api-client'
import * as authApi from '@/api/auth'
import { ThemeToggle } from '@hubra/ui'
import { themeLabels, useLang } from '@/lang'

async function signOut() {
  await authApi.logout()
  clearTokens()
  window.location.assign('/login')
}

/**
 * The frame of the signed-in pages: a white top bar (logo, "Meine Vereine",
 * "Mein Konto", sign-out) over a centred column. `actions` sits above the
 * content, e.g. a back link.
 */
export function SignedInFrame({
  width = 560,
  actions,
  children,
}: {
  width?: number
  actions?: ReactNode
  children: ReactNode
}) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { tr } = useLang()
  // Shares its query with the notifications tab, so both stay in step.
  const notifications = useQuery({
    queryKey: ['notifications'],
    queryFn: authApi.getNotifications,
    refetchInterval: 60_000,
  })
  const unread = notifications.data?.meta.unread ?? 0
  const onNotifications = pathname === '/account/benachrichtigungen'
  const nav = [
    { path: '/clubs', label: tr('Meine Vereine', 'My clubs'), icon: <IconBuildingCommunity size={18} /> },
    { path: '/account', label: tr('Mein Konto', 'My account'), icon: <IconUserCircle size={18} /> },
  ]

  return (
    <div className="graph-bg" style={{ minHeight: '100vh' }}>
      <header className="sso-topbar">
        <Group
          justify="space-between"
          wrap="nowrap"
          style={{ maxWidth: Math.max(width, 720), margin: '0 auto', height: '100%', padding: '0 16px' }}
        >
          <Group
            gap={10}
            wrap="nowrap"
            style={{ cursor: 'pointer' }}
            onClick={() => navigate('/clubs')}
          >
            <div className="logo-mark" />
            <Text fz={20} className="wordmark">
              hubra
            </Text>
          </Group>
          <Group gap={4} wrap="nowrap">
            {nav.map((item) => {
              const active = pathname === item.path || pathname.startsWith(item.path + '/')
              return (
                <Button
                  key={item.path}
                  variant={active ? 'light' : 'subtle'}
                  color={active ? 'acc' : 'gray'}
                  size="sm"
                  px={10}
                  leftSection={item.icon}
                  onClick={() => navigate(item.path)}
                  aria-current={active ? 'page' : undefined}
                  // On a phone only the icon shows.
                  aria-label={item.label}
                >
                  <Box component="span" visibleFrom="xs">
                    {item.label}
                  </Box>
                </Button>
              )
            })}
            <ActionIcon
              variant={onNotifications ? 'light' : 'subtle'}
              color={onNotifications ? 'acc' : 'gray'}
              size={36}
              onClick={() => navigate('/account/benachrichtigungen')}
              aria-label={
                unread > 0
                  ? tr(`Benachrichtigungen, ${unread} ungelesen`, `Notifications, ${unread} unread`)
                  : tr('Benachrichtigungen', 'Notifications')
              }
              title={tr('Benachrichtigungen', 'Notifications')}
            >
              <Indicator
                disabled={unread === 0}
                label={unread > 99 ? '99+' : unread}
                color="red"
                size={16}
                offset={2}
                withBorder
                styles={{ indicator: { fontSize: 10, fontWeight: 700, padding: '0 4px' } }}
              >
                <IconBell size={18} style={{ display: 'block' }} />
              </Indicator>
            </ActionIcon>
            <ThemeToggle labels={themeLabels(tr)} />
            <ActionIcon
              variant="subtle"
              color="gray"
              size={36}
              onClick={signOut}
              aria-label={tr('Abmelden', 'Sign out')}
              title={tr('Abmelden', 'Sign out')}
            >
              <IconLogout size={18} />
            </ActionIcon>
          </Group>
        </Group>
      </header>
      <Box style={{ width: '100%', maxWidth: width, margin: '0 auto', padding: '32px 16px 64px' }}>
        {actions && (
          <Group gap={4} mb="md" ml={-10}>
            {actions}
          </Group>
        )}
        {children}
      </Box>
    </div>
  )
}
