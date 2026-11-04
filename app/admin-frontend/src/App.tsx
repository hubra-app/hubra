import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { ErrorBoundary as RouteErrorBoundary } from 'react-error-boundary'
import { Center, Loader, Paper, Stack, Text, Button } from '@mantine/core'
import { IconAlertTriangle } from '@tabler/icons-react'
import { AdminProvider, useAdmin } from '@/context/AdminContext'
import { StepUpDialog } from '@/components/StepUpDialog'
import { Shell } from '@/components/Shell'
import { TabbedPage } from '@/components/TabbedPage'
import { TenantDetail } from '@/screens/TenantDetail'
import { ClubAdmins } from '@/screens/ClubAdmins'
import { SupportCases } from '@/screens/platform/Support'
import { LEGACY_REDIRECTS, navSections } from '@/nav'
import { SSO_URL, redirectTo } from '@hubra/api-client'
import { useLang } from '@/lang'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { authStatus } = useAdmin()

  useEffect(() => {
    if (authStatus === 'anon') {
      redirectTo(`${SSO_URL}/login?redirect=${encodeURIComponent(window.location.href)}`, 'anon')
    }
  }, [authStatus])

  if (authStatus === 'loading' || authStatus === 'anon')
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    )

  return <>{children}</>
}

function RequireGlobalPermission({ perm, children }: { perm: string; children: React.ReactNode }) {
  const { authStatus, hasGlobalPermission } = useAdmin()
  const { tr } = useLang()

  useEffect(() => {
    if (authStatus === 'anon') {
      redirectTo(`${SSO_URL}/login?redirect=${encodeURIComponent(window.location.href)}`, 'anon')
    }
  }, [authStatus])

  if (authStatus === 'loading' || authStatus === 'anon')
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    )

  if (!hasGlobalPermission(perm))
    return (
      <Center h="100vh">
        <Paper shadow="lg" p="xl" maw={400}>
          <Stack gap="sm" align="center" ta="center">
            <IconAlertTriangle size={40} color="var(--mantine-color-red-text)" />
            <Text fw={700} c="red">
              {tr('Kein Zugriff', 'Access denied')}
            </Text>
            <Text size="sm" c="dimmed">
              {tr('Du hast keine Berechtigung für diese Seite.', 'You do not have permission to access this page.')}
            </Text>
            <Button component="a" href="/app/my-tenants" variant="light" mt="xs">
              {tr('Zu meinen Vereinen', 'To my clubs')}
            </Button>
          </Stack>
        </Paper>
      </Center>
    )

  return <>{children}</>
}

// Club requests used to be asked for here; people now do that on SSO
// (/start), and staff review them under All clubs › Requests.
function ClubRequestsRoute() {
  const { hasGlobalPermission } = useAdmin()
  const location = useLocation()
  const staff = hasGlobalPermission('requests.read.all')
  useEffect(() => {
    if (!staff) redirectTo(`${SSO_URL}/start`, 'not-staff')
  }, [staff])
  if (!staff)
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    )
  return <Navigate to={`/app/tenants/requests${location.search}`} replace />
}

/** An old URL: go to where the page lives now, keeping ?filters. */
function LegacyRedirect({ to }: { to: string }) {
  const location = useLocation()
  return <Navigate to={`${to}${location.search}${location.hash}`} replace />
}

function SsoLoginRedirect() {
  useEffect(() => {
    redirectTo(`${SSO_URL}/login`, 'sso-login')
  }, [])
  return (
    <Center h="100vh">
      <Loader />
    </Center>
  )
}

function DefaultRoute() {
  const { authStatus, isSuperadmin, hasGlobalPermission } = useAdmin()
  // Wait for the permissions, or managers land on My Clubs instead of Tenants.
  if (authStatus !== 'authed')
    return (
      <RequireAuth>
        <Center h="100vh">
          <Loader />
        </Center>
      </RequireAuth>
    )
  if (hasGlobalPermission?.('tenants.read') || isSuperadmin) {
    return <Navigate to="/app/tenants" replace />
  }
  return <Navigate to="/app/my-tenants" replace />
}

function AppRoutes() {
  const { tr } = useLang()
  return (
    <RouteErrorBoundary
      onReset={() => window.location.reload()}
      fallbackRender={({ resetErrorBoundary }) => (
        <Center h="100vh" p="lg">
          <Paper shadow="lg" p="xl" maw={460}>
            <Stack gap="sm" align="center">
              <IconAlertTriangle size={40} color="var(--mantine-color-red-text)" />
              <Text fz={18} fw={700} c="red">
                {tr('Etwas ist schiefgelaufen', 'Something went wrong')}
              </Text>
              <Text size="sm" c="dimmed" ta="center">
                {tr('Ein unerwarteter Fehler ist aufgetreten. Bitte versuche es nochmals.', 'An unexpected error occurred. Please try again.')}
              </Text>
              <Button onClick={() => resetErrorBoundary()}>{tr('Nochmals versuchen', 'Try again')}</Button>
            </Stack>
          </Paper>
        </Center>
      )}
    >
      <Routes>
        <Route path="/login" element={<SsoLoginRedirect />} />
        {navSections().flatMap((section) =>
          section.pages.flatMap((page) =>
            page.tabs.map((tab) => (
              <Route
                key={tab.path}
                path={tab.path}
                element={
                  <RequireAuth>
                    <Shell>
                      <TabbedPage page={page} tab={tab} />
                    </Shell>
                  </RequireAuth>
                }
              />
            )),
          ),
        )}
        {Object.entries(LEGACY_REDIRECTS).map(([from, to]) => (
          <Route key={from} path={from} element={<LegacyRedirect to={to} />} />
        ))}
        <Route
          path="/app/requests"
          element={
            <RequireAuth>
              <ClubRequestsRoute />
            </RequireAuth>
          }
        />
        <Route
          path="/app/tenants/:id"
          element={
            <RequireGlobalPermission perm="tenants.read">
              <Shell>
                <TenantDetail />
              </Shell>
            </RequireGlobalPermission>
          }
        />
        <Route
          path="/app/reports/:id"
          element={
            <RequireGlobalPermission perm="support.cases">
              <Shell>
                <SupportCases />
              </Shell>
            </RequireGlobalPermission>
          }
        />
        <Route
          path="/app/clubs/:id/admins"
          element={
            <RequireAuth>
              <Shell>
                <ClubAdmins />
              </Shell>
            </RequireAuth>
          }
        />
        <Route path="/" element={<DefaultRoute />} />
        <Route path="*" element={<DefaultRoute />} />
      </Routes>
    </RouteErrorBoundary>
  )
}

export default function App() {
  // Remount on a language switch so every screen picks up the new texts.
  const { lang } = useLang()
  return (
    <AdminProvider>
      <StepUpDialog />
      <AppRoutes key={lang} />
    </AdminProvider>
  )
}
