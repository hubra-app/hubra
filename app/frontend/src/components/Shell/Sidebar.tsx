import { ScrollArea, Box, Stack } from '@mantine/core'
import { useNav } from '@/context/AppContext'
import { NavItemRow, NavMoreRow, NavSectionLabel } from './NavItemRow'
import { setCustomizeSidebarOpen } from './customizeSidebarStore'
import { UserCard } from './UserCard'
import { useSidebarNav } from './useSidebarNav'

export function Sidebar() {
  const { go, sidebarCollapsed, userMenuOpen, setUserMenuOpen } = useNav()
  const { nav, activePath, currentMore } = useSidebarNav()

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
        <Stack
          gap={sidebarCollapsed ? 12 : 20}
          p={sidebarCollapsed ? 0 : 'sm'}
          pt={sidebarCollapsed ? 0 : 'md'}
        >
          {nav.map((section, s) => (
            <Box key={section.label}>
              {!sidebarCollapsed && (
                <NavSectionLabel
                  label={section.label}
                  onEdit={s === 0 ? () => setCustomizeSidebarOpen(true) : undefined}
                />
              )}
              <Stack gap={sidebarCollapsed ? 8 : 2}>
                {section.items.map((item) =>
                  item.children && !sidebarCollapsed ? (
                    <NavMoreRow
                      key={item.path}
                      item={item}
                      activePath={activePath}
                      currentMore={currentMore}
                      go={go}
                    />
                  ) : (
                    <NavItemRow
                      key={item.path}
                      item={item}
                      activePath={activePath}
                      go={go}
                      collapsed={sidebarCollapsed}
                    />
                  ),
                )}
              </Stack>
            </Box>
          ))}
        </Stack>
      </ScrollArea>

      {!sidebarCollapsed && (
        <Box p="xs" style={{ borderTop: '1px solid var(--hb-border)' }}>
          <UserCard opened={userMenuOpen} onChange={setUserMenuOpen} />
        </Box>
      )}
    </Box>
  )
}
