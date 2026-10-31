import { useEffect } from 'react'
import { AppShell } from '@mantine/core'
import { useElementSize } from '@mantine/hooks'
import { useAuth, useNav } from '@/context/AppContext'
import { ForcedPasswordChangeModal } from '@/components/ForcedPasswordChangeModal'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { MobileDrawer } from './MobileDrawer'
import { NotificationPanel } from './NotificationPanel'
import { ImpersonationBanner } from './ImpersonationBanner'
import { ClubBanner } from './ClubBanner'
import { ClubBranding } from './ClubBranding'

export function Shell({ children }: { children: React.ReactNode }) {
  const { currentUser } = useAuth()
  const { sidebarCollapsed } = useNav()
  // The support banner sits above the top bar; the header grows with it so
  // it doesn't cover the top of the page.
  const { ref: bannerRef, height: bannerHeight } = useElementSize()
  const headerHeight = 64 + Math.ceil(bannerHeight)
  // Side panels (SlideOver) open below the top bar.
  useEffect(() => {
    document.documentElement.style.setProperty('--hb-header-h', `${headerHeight}px`)
  }, [headerHeight])

  return (
    <AppShell
      navbar={{
        width: { base: 244, sm: sidebarCollapsed ? 64 : 244 },
        breakpoint: 'sm',
        collapsed: { mobile: true, desktop: false },
      }}
      header={{ height: headerHeight }}
      padding={0}
      styles={{
        main: {
          background: 'var(--hb-page)',
          // Border-box: the header's padding-top is inside this height.
          height: '100dvh',
          minHeight: '100dvh',
          overflowY: 'auto',
        },
      }}
    >
      <AppShell.Header>
        <div ref={bannerRef}>
          <ImpersonationBanner />
        </div>
        <TopBar />
      </AppShell.Header>

      <AppShell.Navbar>
        <Sidebar />
      </AppShell.Navbar>

      <MobileDrawer />

      <AppShell.Main>
        <ClubBanner />
        <div className="page-container">{children}</div>
      </AppShell.Main>

      <ClubBranding />
      <NotificationPanel />
      {currentUser?.mustChangePassword && <ForcedPasswordChangeModal />}
    </AppShell>
  )
}
