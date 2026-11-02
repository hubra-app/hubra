import { useState } from 'react'
import { Drawer, ScrollArea, Group, Box, Stack, ActionIcon } from '@mantine/core'
import { IconX } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useNav, useAuth } from '@/context/AppContext'
import { NavItemRow, NavMoreRow, NavSectionLabel } from './NavItemRow'
import { setCustomizeSidebarOpen } from './customizeSidebarStore'
import { UserCard } from './UserCard'
import { ClubMark } from './ClubMark'
import { LanguageSwitcher } from '@/components/LanguageSwitcher'
import { useSidebarNav } from './useSidebarNav'

export function MobileDrawer() {
  const { t } = useT()
  const { go, mobileDrawerOpen, setMobileDrawerOpen } = useNav()
  const { currentUser } = useAuth()
  const { nav, activePath, currentMore } = useSidebarNav()
  // The phone menu's own account menu; the desktop sidebar (hidden here but
  // still mounted) keeps the shared one.
  const [accountOpen, setAccountOpen] = useState(false)
  const close = () => {
    setAccountOpen(false)
    setMobileDrawerOpen(false)
  }

  return (
    <Drawer
      opened={mobileDrawerOpen}
      onClose={close}
      // However it closed (a nav entry, a tap beside it), it opens again
      // with the account menu folded.
      onExitTransitionEnd={() => setAccountOpen(false)}
      // A side panel over a dimmed page, not a full-screen sheet: the page
      // stays in view and a tap beside the panel closes it.
      position="left"
      size="min(300px, 85vw)"
      padding={0}
      withCloseButton={false}
      // Header, scrolling nav, then the user card pinned at the foot: the
      // card stays in view however far the nav scrolls. The panel is as tall
      // as the visible screen (not 100vh, which on phones runs on under the
      // browser's toolbar and hid the foot of the menu).
      styles={{
        content: {
          background: 'var(--hb-sidebar)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        },
        body: {
          flex: 1,
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
        },
      }}
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
          onClick={close}
          aria-label={t('common.close', 'Schliessen')}
        >
          <IconX size={20} />
        </ActionIcon>
      </Group>

      <ScrollArea flex={1} type="auto">
        <Stack gap={16} p="sm">
          {nav.map((section, s) => (
            <Box key={section.label}>
              <NavSectionLabel
                label={section.label}
                onEdit={
                  s === 0 && currentUser
                    ? () => {
                        close()
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

      {currentUser && (
        <Box
          p="xs"
          style={{ borderTop: '1px solid var(--hb-border)', flexShrink: 0 }}
          // Every entry of the account menu leads somewhere else, so close the
          // phone menu with it (the theme switch is radios, not buttons, and
          // stays).
          onClick={(e) => {
            const el = e.target as HTMLElement
            if (el.closest('[data-testid="user-menu"] button')) close()
          }}
        >
          <UserCard opened={accountOpen} onChange={setAccountOpen} />
        </Box>
      )}
    </Drawer>
  )
}
