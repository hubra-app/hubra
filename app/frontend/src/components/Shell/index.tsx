import { AppShell } from '@mantine/core'
import { useAuth, useNav } from '@/context/AppContext'
import { ForcedPasswordChangeModal } from '@/components/ForcedPasswordChangeModal'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { MobileDrawer } from './MobileDrawer'
import { NotificationPanel } from './NotificationPanel'
import { ImpersonationBanner } from './ImpersonationBanner'

export function Shell({ children }: { children: React.ReactNode }) {
  const { currentUser } = useAuth()
  const { sidebarCollapsed } = useNav()

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
        <div style={{ padding: 'var(--mantine-spacing-xl)' }}>{children}</div>
      </AppShell.Main>

      <NotificationPanel />
      {currentUser?.mustChangePassword && <ForcedPasswordChangeModal />}
    </AppShell>
  )
}
