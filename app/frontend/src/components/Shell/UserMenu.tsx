import { Group, Text, Avatar, Divider, Box, UnstyledButton, Stack, ScrollArea } from '@mantine/core'
import {
  IconLogout,
  IconBuilding,
  IconUserCircle,
  IconSparkles,
  IconPalette,
  IconBug,
  IconBulb,
  IconLifebuoy,
} from '@tabler/icons-react'
import { ThemeSwitch } from '@hubra/ui'
import { useT } from '@/locales/i18n'
import { useAuth, useNav, useData } from '@/context/AppContext'
import { useInstance } from '@/context/InstanceContext'
import { useMyTenants } from '@/data/lists'
import { initials, contrastColor } from './nav'
import { setWhatsNewOpen } from './whatsNewStore'
import { openReport } from '@/screens/private/support/reportStore'
import { useWhatsNewUnseen } from './whatsNewData'

/** Help, roadmap, status and reports (app/support-frontend). */
const SUPPORT_URL = import.meta.env.VITE_SUPPORT_URL ?? 'https://support.hubra.club'

const rowStyle = {
  display: 'flex',
  alignItems: 'center',
  gap: 10,
  width: '100%',
  height: 36,
  padding: '0 10px',
  fontSize: 'var(--mantine-font-size-sm)',
  borderRadius: 8,
} as const

/**
 * The account menu, a pop-over above the user card (sidebar and phone menu)
 * or below the top bar's avatar. `onClose` closes it; by default that is the
 * shared user-menu state.
 *
 * It holds only what the card and the sidebar don't: club switch, account,
 * news, appearance, sign-out. The user card already names who is signed in,
 * so the name block only shows under the top bar's avatar (`withHeader`);
 * the club profile is a sidebar entry and the pencil there customises it.
 */
export function UserMenu({
  onClose,
  withHeader = false,
}: { onClose?: () => void; withHeader?: boolean } = {}) {
  const { t } = useT()
  const { setPhase, currentUser } = useAuth()
  const { setUserMenuOpen } = useNav()
  const { ssoUrl } = useInstance()
  const { switchTenant } = useData()
  const myTenants = useMyTenants()
  const name = currentUser?.name ?? ''
  const email = currentUser?.publicEmail || currentUser?.email || ''
  const bg = currentUser?.avatarColor ?? '#ebe8f2'
  const close = onClose ?? (() => setUserMenuOpen(false))
  const whatsNewUnseen = useWhatsNewUnseen()

  return (
    <Box
      data-testid="user-menu"
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
      {withHeader && (
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
      )}
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
                      close()
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
            style={rowStyle}
          >
            <IconUserCircle size={16} />
            {t('shell.userMenu.account')}
          </UnstyledButton>
          <UnstyledButton
            onClick={() => {
              setWhatsNewOpen(true)
              close()
            }}
            style={rowStyle}
          >
            <IconSparkles size={16} />
            {t('shell.whatsNew.title')}
            {whatsNewUnseen && (
              // A dot, not a word: the entry keeps its name for screen readers and tests.
              <Box
                component="span"
                data-testid="whats-new-unseen"
                title={t('shell.whatsNew.new', 'Neu')}
                aria-hidden
                w={8}
                h={8}
                ml="auto"
                style={{ borderRadius: 99, background: 'var(--mantine-primary-color-filled)', flexShrink: 0 }}
              />
            )}
          </UnstyledButton>
        </Stack>
        <Divider my={6} />
        <Stack gap={0}>
          <UnstyledButton
            data-testid="menu-report-bug"
            onClick={() => {
              openReport('bug')
              close()
            }}
            style={rowStyle}
          >
            <IconBug size={16} />
            {t('support.menu.bug', 'Problem melden')}
          </UnstyledButton>
          <UnstyledButton
            data-testid="menu-report-feature"
            onClick={() => {
              openReport('feature')
              close()
            }}
            style={rowStyle}
          >
            <IconBulb size={16} />
            {t('support.menu.feature', 'Idee vorschlagen')}
          </UnstyledButton>
          <UnstyledButton
            component="a"
            href={SUPPORT_URL}
            target="_blank"
            rel="noopener"
            onClick={close}
            style={rowStyle}
          >
            <IconLifebuoy size={16} />
            {t('support.menu.help', 'Hilfe und Support')}
          </UnstyledButton>
        </Stack>
        <Group justify="space-between" px={10} py={6} wrap="nowrap">
          <Group gap={10} wrap="nowrap">
            <IconPalette size={16} />
            <Text fz="sm">{t('shell.userMenu.appearance', 'Darstellung')}</Text>
          </Group>
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
            close()
          }}
          style={{ ...rowStyle, color: 'var(--mantine-color-red-6)' }}
        >
          <IconLogout size={16} />
          {t('shell.userMenu.logout')}
        </UnstyledButton>
      </Box>
    </Box>
  )
}
