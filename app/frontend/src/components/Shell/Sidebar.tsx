import { ScrollArea, Text, Box, UnstyledButton, Stack } from '@mantine/core'
import { IconDotsVertical } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useLocation } from 'react-router-dom'
import { useNav, useAuth, useData } from '@/context/AppContext'
import { NavItemRow } from './NavItemRow'
import { UserMenu } from './UserMenu'
import { usePlugins } from '@/plugins/store'
import { buildNav, filterNav, initials, contrastColor } from './nav'

export function Sidebar() {
  const { t } = useT()
  const location = useLocation()
  const { go, sidebarCollapsed, userMenuOpen, setUserMenuOpen } = useNav()
  const { currentUser, hasPermission } = useAuth()
  const {
    memberCount,
    pendingApplicationCount,
    groupCount,
    polls,
    openInvoiceCount,
    moduleList,
  } = useData()
  const openPolls = polls.filter((p) => p.status === 'open').length
  usePlugins() // plugin icons arrive after the first render
  const nav = filterNav(
    buildNav(
      {
        members: memberCount,
        applications: pendingApplicationCount,
        groups: groupCount,
        polls: openPolls,
        invoices: openInvoiceCount,
      },
      t,
      moduleList,
    ),
    hasPermission,
  )
  const userName = currentUser?.name ?? ''
  const userRole = currentUser?.roles?.join(', ') ?? ''
  const userBg = currentUser?.avatarColor ?? '#e7eeea'

  return (
    <Box
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--mantine-color-white)',
      }}
    >
      <ScrollArea
        flex={1}
        type="auto"
        offsetScrollbars
        styles={
          sidebarCollapsed
            ? {
                viewport: { padding: '10px 8px' },
                scrollbar: { display: 'none' },
              }
            : undefined
        }
      >
        <Stack gap={sidebarCollapsed ? 12 : 16} p={sidebarCollapsed ? 0 : 'xs'}>
          {nav.map((section) => (
            <Box key={section.label}>
              {!sidebarCollapsed && (
                <Text
                  fz="xs"
                  fw={600}
                  c="dimmed"
                  tt="uppercase"
                  style={{
                    letterSpacing: '0.10em',
                    padding: '0 11px',
                    marginBottom: 4,
                  }}
                >
                  {section.label}
                </Text>
              )}
              <Stack gap={sidebarCollapsed ? 8 : 2}>
                {section.items.map((item) => (
                  <NavItemRow
                    key={item.path}
                    item={item}
                    pathname={location.pathname}
                    go={go}
                    collapsed={sidebarCollapsed}
                  />
                ))}
              </Stack>
            </Box>
          ))}
        </Stack>
      </ScrollArea>

      {!sidebarCollapsed && (
        <Box
          p="xs"
          style={{
            borderTop: '1px solid var(--mantine-color-gray-3)',
            position: 'relative',
          }}
        >
          {userMenuOpen && <UserMenu />}
          <UnstyledButton
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: sidebarCollapsed ? 'center' : 'flex-start',
              gap: 10,
              height: 42,
              padding: '0 10px',
              borderRadius: 10,
              background: 'var(--mantine-color-gray-1)',
            }}
          >
            <Box
              style={{
                width: 34,
                height: 34,
                borderRadius: '50%',
                background: userBg,
                fontSize: 'var(--mantine-font-size-xs)',
                fontWeight: 700,
                color: contrastColor(userBg),
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              {initials(userName)}
            </Box>
            {!sidebarCollapsed && (
              <>
                <Box style={{ flex: 1, textAlign: 'left', minWidth: 0 }}>
                  <Text fz="sm" fw={600} lh={1.2}>
                    {userName}
                  </Text>
                  <Text fz="xs" c="dimmed" opacity={0.65}>
                    {userRole}
                  </Text>
                </Box>
                <IconDotsVertical
                  size={16}
                  style={{
                    color: 'var(--mantine-color-dimmed)',
                    flexShrink: 0,
                  }}
                />
              </>
            )}
          </UnstyledButton>
        </Box>
      )}
    </Box>
  )
}
