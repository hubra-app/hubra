import { Drawer, ScrollArea, Group, Box, Stack, ActionIcon } from '@mantine/core'
import { IconX } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useNav, useAuth } from '@/context/AppContext'
import { NavItemRow, NavMoreRow, NavSectionLabel } from './NavItemRow'
import { setCustomizeSidebarOpen } from './customizeSidebarStore'
import { UserMenu } from './UserMenu'
import { ClubMark } from './ClubMark'
import { LanguageSwitcher } from '@/components/LanguageSwitcher'
import { useSidebarNav } from './useSidebarNav'

export function MobileDrawer() {
  const { t } = useT()
  const { go, mobileDrawerOpen, setMobileDrawerOpen } = useNav()
  const { currentUser } = useAuth()
  const { nav, activePath, currentMore } = useSidebarNav()

  return (
    <Drawer
      opened={mobileDrawerOpen}
      onClose={() => setMobileDrawerOpen(false)}
      // A side panel over a dimmed page, not a full-screen sheet: the page
      // stays in view and a tap beside the panel closes it.
      position="left"
      size="min(300px, 85vw)"
      padding={0}
      withCloseButton={false}
      styles={{ content: { background: 'var(--hb-sidebar)' } }}
    >
      <Group
        gap={10}
        px={16}
        h={56}
        justify="space-between"
        style={{
          borderBottom: '1px solid var(--hb-border)',
          flexShrink: 0,
        }}
        wrap="nowrap"
      >
        <ClubMark />
        <ActionIcon
          variant="subtle"
          size="lg"
          onClick={() => setMobileDrawerOpen(false)}
          aria-label={t('common.close', 'Schliessen')}
        >
          <IconX size={20} />
        </ActionIcon>
      </Group>

      <ScrollArea h="calc(100vh - 56px)" type="auto">
        <Stack gap={16} p="sm">
          {nav.map((section, s) => (
            <Box key={section.label}>
              <NavSectionLabel
                label={section.label}
                onEdit={
                  s === 0 && currentUser
                    ? () => {
                        setMobileDrawerOpen(false)
                        setCustomizeSidebarOpen(true)
                      }
                    : undefined
                }
              />
              <Stack gap={2}>
                {section.items.map((item) =>
                  item.children ? (
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
                      collapsed={false}
                    />
                  ),
                )}
              </Stack>
            </Box>
          ))}
        </Stack>

        {currentUser && (
          <Box
            p="sm"
            style={{
              borderTop: '1px solid var(--hb-border)',
            }}
            // Every entry of the menu leads somewhere else, so close the menu
            // with it (the theme switch is radios, not buttons, and stays).
            onClick={(e) => {
              if ((e.target as HTMLElement).closest('button')) setMobileDrawerOpen(false)
            }}
          >
            <UserMenu inline />
          </Box>
        )}

        <Box
          p="sm"
          style={{
            borderTop: '1px solid var(--hb-border)',
            display: 'flex',
            justifyContent: 'center',
          }}
        >
          <LanguageSwitcher />
        </Box>
      </ScrollArea>
    </Drawer>
  )
}
