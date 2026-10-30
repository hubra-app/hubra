import {
  Group,
  Text,
  Avatar,
  Divider,
  Box,
  UnstyledButton,
  Stack,
  ScrollArea,
} from '@mantine/core'
import {
  IconLogout,
  IconBuilding,
} from '@tabler/icons-react'
import { ThemeSwitch } from '@hubra/ui'
import { useT } from '@/locales/i18n'
import { useAuth, useNav, useData } from '@/context/AppContext'
import { useInstance } from '@/context/InstanceContext'
import { useMyTenants } from '@/data/lists'
import { initials, contrastColor } from './nav'
import { setWhatsNewOpen } from './whatsNewStore'

export function UserMenu() {
  const { t } = useT()
  const { setPhase, currentUser } = useAuth()
  const { go, setUserMenuOpen } = useNav()
  const { ssoUrl } = useInstance()
  const { switchTenant } = useData()
  const myTenants = useMyTenants()
  const name = currentUser?.name ?? ''
  const email = currentUser?.publicEmail || currentUser?.email || ''
  const bg = currentUser?.avatarColor ?? '#ebe8f2'
  // Light, dark or the device's setting; Mantine keeps it in this browser.

  return (
    <Box
      style={{
        position: 'absolute',
        bottom: '100%',
        left: 0,
        right: 0,
        marginBottom: 8,
        background: 'var(--hb-surface)',
        border: '1px solid var(--mantine-color-gray-5)',
        borderRadius: 13,
        boxShadow: '0 26px 64px -22px rgba(26,22,37,.28), 0 4px 14px -6px rgba(26,22,37,.15)',
        zIndex: 60,
        overflow: 'hidden',
      }}
    >
      <Group gap="sm" p="md" style={{ borderBottom: '1px solid var(--hb-border)' }}>
        <Avatar
          size={38}
          radius="xl"
          styles={{
            root: {
              backgroundColor: bg,
              color: contrastColor(bg),
              fontWeight: 700,
            },
          }}
        >
          {initials(name)}
        </Avatar>
        <Box style={{ minWidth: 0 }}>
          <Text fz="sm" fw={600}>
            {name}
          </Text>
          <Text fz="xs" c="dimmed">
            {email}
          </Text>
        </Box>
      </Group>
      {myTenants.length > 1 && (
        <>
          <Box px="md" pt="sm" pb={4}>
            <Text fz="xs" fw={600} c="dimmed" tt="uppercase" lh={1}>
              {t('shell.userMenu.clubs', 'Vereine')}
            </Text>
          </Box>
          <ScrollArea.Autosize mah={160} offsetScrollbars>
            <Stack gap={0} px={6}>
              {myTenants.map((tenant) => (
                <UnstyledButton
                  key={tenant.tenant_slug}
                  onClick={() => {
                    if (tenant.tenant_slug) {
                      switchTenant(tenant.tenant_slug)
                      setUserMenuOpen(false)
                    }
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    height: 32,
                    padding: '0 10px',
                    fontSize: 'var(--mantine-font-size-sm)',
                    borderRadius: 8,
                  }}
                >
                  <IconBuilding size={14} />
                  {tenant.tenant_name ?? tenant.tenant_slug}
                </UnstyledButton>
              ))}
            </Stack>
          </ScrollArea.Autosize>
          <Divider my={6} />
        </>
      )}
      <Box p={6}>
        <Stack gap={0}>
          <UnstyledButton
            onClick={() => {
              // The account (name, email, password, sessions) lives on SSO.
              window.location.assign(`${ssoUrl}/account`)
            }}
            style={{
              height: 36,
              padding: '0 10px',
              fontSize: 'var(--mantine-font-size-sm)',
              borderRadius: 8,
            }}
          >
            {t('shell.userMenu.account')}
          </UnstyledButton>
          <UnstyledButton
            onClick={() => {
              go('/app/account/settings')
              setUserMenuOpen(false)
            }}
            style={{
              height: 36,
              padding: '0 10px',
              fontSize: 'var(--mantine-font-size-sm)',
              borderRadius: 8,
            }}
          >
            {t('shell.userMenu.accountSettings')}
          </UnstyledButton>
          <UnstyledButton
            onClick={() => {
              setWhatsNewOpen(true)
              setUserMenuOpen(false)
            }}
            style={{
              height: 36,
              padding: '0 10px',
              fontSize: 'var(--mantine-font-size-sm)',
              borderRadius: 8,
            }}
          >
            {t('shell.whatsNew.title')}
          </UnstyledButton>
        </Stack>
        <Group justify="space-between" px={10} py={6} wrap="nowrap">
          <Text fz="sm">{t('shell.userMenu.appearance', 'Darstellung')}</Text>
          <ThemeSwitch
            labels={{
              light: t('shell.userMenu.light', 'Hell'),
              dark: t('shell.userMenu.dark', 'Dunkel'),
              system: t('shell.userMenu.system', 'Wie Gerät'),
            }}
          />
        </Group>
        <Divider my={6} />
        <UnstyledButton
          onClick={() => {
            setPhase('login')
            setUserMenuOpen(false)
          }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            height: 36,
            padding: '0 10px',
            fontSize: 'var(--mantine-font-size-sm)',
            color: 'var(--mantine-color-red-6)',
            borderRadius: 8,
          }}
        >
          <IconLogout size={16} />
          {t('shell.userMenu.logout')}
        </UnstyledButton>
      </Box>
    </Box>
  )
}
