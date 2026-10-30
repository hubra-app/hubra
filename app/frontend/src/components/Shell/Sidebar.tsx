import { ScrollArea, Text, Box, UnstyledButton, Stack } from '@mantine/core'
import { IconDotsVertical } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useLocation } from 'react-router-dom'
import { useNav, useAuth, useData } from '@/context/AppContext'
import { NavItemRow } from './NavItemRow'
import { UserMenu } from './UserMenu'
import { usePlugins } from '@/plugins/store'
import { useNavCounts } from '@/data/lists'
import { buildNav, filterNav, getParentPath, initials, contrastColor } from './nav'
import { roleLabels } from '@/roles'

export function Sidebar() {
  const { t } = useT()
  const location = useLocation()
  const { go, sidebarCollapsed, userMenuOpen, setUserMenuOpen } = useNav()
  const { currentUser, hasPermission } = useAuth()
  const { moduleList } = useData()
  const counts = useNavCounts()
  usePlugins() // plugin icons arrive after the first render
  const nav = filterNav(
    buildNav(
      counts,
      t,
      moduleList,
    ),
    hasPermission,
  )
  const activePath = getParentPath(
    location.pathname,
    nav.flatMap((section) => section.items.map((item) => item.path)),
  )
  const userName = currentUser?.name ?? ''
  const userRole = roleLabels(currentUser?.roles)
  const userBg = currentUser?.avatarColor ?? '#ebe8f2'

  return (
    <Box
      style={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--hb-sidebar)',
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
        <Stack gap={sidebarCollapsed ? 12 : 20} p={sidebarCollapsed ? 0 : 'sm'} pt={sidebarCollapsed ? 0 : 'md'}>
          {nav.map((section) => (
            <Box key={section.label}>
              {!sidebarCollapsed && (
                <Text
                  fz={11}
                  fw={700}
                  c="gray.6"
                  tt="uppercase"
                  style={{
                    letterSpacing: '0.08em',
                    padding: '0 12px',
                    marginBottom: 6,
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
                    active={activePath === item.path}
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
            borderTop: '1px solid var(--hb-border)',
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
                  <Text fz="sm" fw={600} lh={1.2} truncate>
                    {userName}
                  </Text>
                  <Text fz="xs" c="dimmed" truncate>
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
