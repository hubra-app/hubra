import { useState, useCallback } from 'react'
import { AppShell, Button, Text } from '@mantine/core'
import { IconMailExclamation } from '@tabler/icons-react'
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
          background: '#f7f6fb',
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
        <div className="page-container">
          {currentUser && !currentUser.privateEmailVerified && (
            <div className="verify-banner" role="status">
              <IconMailExclamation size={20} color="#8a6a00" style={{ flexShrink: 0 }} />
              <Text size="sm" style={{ flex: '1 1 260px' }}>
                {t('shell.emailVerify.banner')}
              </Text>
              <Button
                size="xs"
                variant="white"
                color="dark"
                style={{ border: '1px solid #fce588' }}
                onClick={handleResendVerification}
                loading={verifySending}
              >
                {t('shell.emailVerify.resend')}
              </Button>
            </div>
          )}
          {children}
        </div>
      </AppShell.Main>

      <NotificationPanel />
      {currentUser?.mustChangePassword && <ForcedPasswordChangeModal />}
    </AppShell>
  )
}
