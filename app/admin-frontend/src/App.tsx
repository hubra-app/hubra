import { useEffect } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { ErrorBoundary as RouteErrorBoundary } from 'react-error-boundary'
import { Center, Loader, Paper, Stack, Text, Button } from '@mantine/core'
import { IconAlertTriangle } from '@tabler/icons-react'
import { AdminProvider, useAdmin } from '@/context/AdminContext'
import { Shell } from '@/components/Shell'
import { AdminPortal } from '@/screens/AdminPortal'
import { MyTenantsTab } from '@/screens/MyTenantsTab'
import { TenantDetail } from '@/screens/TenantDetail'
import { MailRelay } from '@/screens/platform/MailRelay'
import { SSO_URL } from '@hubra/api-client'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { authStatus } = useAdmin()

  useEffect(() => {
    if (authStatus === 'anon') {
      window.location.assign(
        `${SSO_URL}/login?redirect=${encodeURIComponent(window.location.href)}`,
      )
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

  useEffect(() => {
    if (authStatus === 'anon') {
      window.location.assign(
        `${SSO_URL}/login?redirect=${encodeURIComponent(window.location.href)}`,
      )
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
            <IconAlertTriangle size={40} color="#dc2626" />
            <Text fw={700} c="red">
              Access Denied
            </Text>
            <Text size="sm" c="dimmed">
              You do not have permission to access this page.
            </Text>
          </Stack>
        </Paper>
      </Center>
    )

  return <>{children}</>
}

function SsoLoginRedirect() {
  useEffect(() => {
    window.location.assign(`${SSO_URL}/login`)
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
  return (
    <RouteErrorBoundary
      onReset={() => window.location.reload()}
      fallbackRender={({ resetErrorBoundary }) => (
        <Center h="100vh" p="lg">
          <Paper shadow="lg" p="xl" maw={460}>
            <Stack gap="sm" align="center">
              <IconAlertTriangle size={40} color="#dc2626" />
              <Text fz={18} fw={700} c="red">
                Something went wrong
              </Text>
              <Text size="sm" c="dimmed" ta="center">
                An unexpected error occurred. Please try again.
              </Text>
              <Button onClick={() => resetErrorBoundary()}>Retry</Button>
            </Stack>
          </Paper>
        </Center>
      )}
    >
      <Routes>
        <Route path="/login" element={<SsoLoginRedirect />} />
        <Route
          path="/app/my-tenants"
          element={
            <RequireAuth>
              <Shell>
                <MyTenantsTab />
              </Shell>
            </RequireAuth>
          }
        />
        <Route
          path="/app/tenants"
          element={
            <RequireGlobalPermission perm="tenants.read">
              <Shell>
                <AdminPortal />
              </Shell>
            </RequireGlobalPermission>
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
          path="/app/requests"
          element={
            <RequireAuth>
              <Shell>
                <AdminPortal />
              </Shell>
            </RequireAuth>
          }
        />
        <Route
          path="/app/audit"
          element={
            <RequireGlobalPermission perm="audit.read">
              <Shell>
                <AdminPortal />
              </Shell>
            </RequireGlobalPermission>
          }
        />
        <Route
          path="/app/roles"
          element={
            <RequireGlobalPermission perm="roles.manage">
              <Shell>
                <AdminPortal />
              </Shell>
            </RequireGlobalPermission>
          }
        />
        <Route
          path="/app/plugins"
          element={
            <RequireGlobalPermission perm="plugins.manage">
              <Shell>
                <AdminPortal />
              </Shell>
            </RequireGlobalPermission>
          }
        />
        <Route
          path="/app/platform/mail"
          element={
            <RequireGlobalPermission perm="platform.settings">
              <Shell>
                <MailRelay />
              </Shell>
            </RequireGlobalPermission>
          }
        />
        <Route path="/" element={<DefaultRoute />} />
        <Route path="*" element={<DefaultRoute />} />
      </Routes>
    </RouteErrorBoundary>
  )
}

export default function App() {
  return (
    <AdminProvider>
      <AppRoutes />
    </AdminProvider>
  )
}
