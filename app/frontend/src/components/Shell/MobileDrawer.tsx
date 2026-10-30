import {
  Drawer,
  ScrollArea,
  Group,
  Text,
  Box,
  Stack,
  ActionIcon,
} from '@mantine/core'
import { IconX } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useLocation } from 'react-router-dom'
import { useNav, useAuth, useData } from '@/context/AppContext'
import { NavItemRow } from './NavItemRow'
import { UserMenu } from './UserMenu'
import { ClubMark } from './ClubMark'
import { LanguageSwitcher } from '@/components/LanguageSwitcher'
import { usePlugins } from '@/plugins/store'
import { useNavCounts } from '@/data/lists'
import { buildNav, filterNav, getParentPath } from './nav'

export function MobileDrawer() {
  const { t } = useT()
  const location = useLocation()
  const { go, mobileDrawerOpen, setMobileDrawerOpen } = useNav()
  const { hasPermission, currentUser } = useAuth()
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
          {nav.map((section) => (
            <Box key={section.label}>
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
              <Stack gap={2}>
                {section.items.map((item) => (
                  <NavItemRow
                    key={item.path}
                    item={item}
                    active={activePath === item.path}
                    go={go}
                    collapsed={false}
                  />
                ))}
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
          >
            <UserMenu />
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
