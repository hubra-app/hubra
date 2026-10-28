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
import { LanguageSwitcher } from '@/components/LanguageSwitcher'
import { buildNav, filterNav } from './nav'

export function MobileDrawer() {
  const { t } = useT()
  const location = useLocation()
  const { go, mobileDrawerOpen, setMobileDrawerOpen } = useNav()
  const { hasPermission, currentUser } = useAuth()
  const {
    memberCount,
    pendingApplicationCount,
    groupCount,
    polls,
    openInvoiceCount,
    moduleList,
  } = useData()
  const openPolls = polls.filter((p) => p.status === 'open').length
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

  return (
    <Drawer
      opened={mobileDrawerOpen}
      onClose={() => setMobileDrawerOpen(false)}
      position="top"
      size="100%"
      padding={0}
      withCloseButton={false}
      styles={{ content: { background: 'var(--mantine-color-white)' } }}
    >
      <Group
        gap={10}
        px={16}
        h={56}
        justify="space-between"
        style={{
          borderBottom: '1px solid var(--mantine-color-gray-3)',
          flexShrink: 0,
        }}
        wrap="nowrap"
      >
        <Group gap={10} wrap="nowrap">
          <div className="logo-mark" />
          <Text fz="md" fw={700}>
            Hubra
          </Text>
        </Group>
        <ActionIcon
          variant="subtle"
          size="lg"
          onClick={() => setMobileDrawerOpen(false)}
          aria-label="Close"
        >
          <IconX size={20} />
        </ActionIcon>
      </Group>

      <ScrollArea h="calc(100vh - 56px)" type="auto">
        <Stack gap={16} p="sm">
          {nav.map((section) => (
            <Box key={section.label}>
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
              <Stack gap={2}>
                {section.items.map((item) => (
                  <NavItemRow
                    key={item.path}
                    item={item}
                    pathname={location.pathname}
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
              borderTop: '1px solid var(--mantine-color-gray-3)',
            }}
          >
            <UserMenu />
          </Box>
        )}

        <Box
          p="sm"
          style={{
            borderTop: '1px solid var(--mantine-color-gray-3)',
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
