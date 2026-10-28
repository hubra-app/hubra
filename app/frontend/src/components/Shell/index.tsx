import { useState, useCallback } from 'react'
import { AppShell, Alert, Button, Group, Text } from '@mantine/core'
import { IconShieldCheckFilled } from '@tabler/icons-react'
import { useT } from '@/locales/i18n'
import { useAuth, useNav } from '@/context/AppContext'
import { requestEmailVerification } from '@/api/auth'
import { ForcedPasswordChangeModal } from '@/components/ForcedPasswordChangeModal'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { MobileDrawer } from './MobileDrawer'
import { NotificationPanel } from './NotificationPanel'
import { ImpersonationBanner } from './ImpersonationBanner'

export function Shell({ children }: { children: React.ReactNode }) {
  const { t } = useT()
  const { currentUser } = useAuth()
  const { sidebarCollapsed } = useNav()
  const [verifySending, setVerifySending] = useState(false)

  const handleResendVerification = useCallback(async () => {
    setVerifySending(true)
    try {
      await requestEmailVerification()
    } catch {
      /* ignore */
    }
    setVerifySending(false)
  }, [])

  return (
    <AppShell
      navbar={{
        width: { base: 244, sm: sidebarCollapsed ? 64 : 244 },
        breakpoint: 'sm',
        collapsed: { mobile: true, desktop: false },
      }}
      header={{ height: 64 }}
      padding={0}
      styles={{
        main: {
          background: '#eef3f0',
          backgroundImage:
            'linear-gradient(rgba(24,24,24,.08) 1px, transparent 1px), linear-gradient(90deg, rgba(24,24,24,.08) 1px, transparent 1px), linear-gradient(rgba(24,24,24,.05) 1px, transparent 1px), linear-gradient(90deg, rgba(24,24,24,.05) 1px, transparent 1px)',
          backgroundSize: '132px 132px, 132px 132px, 22px 22px, 22px 22px',
          height: 'calc(100vh - 64px)',
          minHeight: 'calc(100vh - 64px)',
          overflowY: 'auto',
        },
      }}
    >
      <AppShell.Header>
        <ImpersonationBanner />
        <TopBar />
      </AppShell.Header>

      <AppShell.Navbar>
        <Sidebar />
      </AppShell.Navbar>

      <MobileDrawer />

      <AppShell.Main>
        {currentUser && !currentUser.privateEmailVerified && (
          <Alert
            icon={<IconShieldCheckFilled size={18} />}
            color="acc"
            variant="filled"
            radius={0}
            styles={{
              root: {
                borderRadius: 0,
                position: 'sticky',
                top: 0,
                zIndex: 10,
              },
            }}
          >
            <Group justify="space-between" gap="md" px="xl">
              <Text size="sm">{t('shell.emailVerify.banner')}</Text>
              <Button
                size="sm"
                variant="default"
                onClick={handleResendVerification}
                loading={verifySending}
              >
                {verifySending ? t('shell.emailVerify.sending') : t('shell.emailVerify.resend')}
              </Button>
            </Group>
          </Alert>
        )}
        <div style={{ padding: 'var(--mantine-spacing-xl)' }}>{children}</div>
      </AppShell.Main>

      <NotificationPanel />
      {currentUser?.mustChangePassword && <ForcedPasswordChangeModal />}
    </AppShell>
  )
}
