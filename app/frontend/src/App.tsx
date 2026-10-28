import { lazy, Suspense, useEffect, useState } from 'react'
import { Navigate, Route, Routes, useLocation, useParams } from 'react-router-dom'
import { ErrorBoundary as RouteErrorBoundary } from 'react-error-boundary'
import { useT } from '@/locales/i18n'
import { AppProvider, useApp } from '@/context/AppContext'
import { RequireModule } from '@/modules/RequireModule'
import { ApplyScreen } from '@/screens/public/Apply'
import { NotFoundScreen } from '@/screens/public/NotFound'
import { Toasts } from '@/components/ui'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { SSO_URL } from '@vollbuild/api-client'
import { IconAlertTriangle, IconRefresh } from '@tabler/icons-react'
import { Loader, Center, Overlay, Paper, Text, Button, Stack } from '@mantine/core'

const Shell = lazy(() => import('./components/Shell').then((m) => ({ default: m.Shell })))

// Lazy-load private screens
const DashboardScreen = lazy(() =>
  import('./screens/private/dashboard/Dashboard').then((m) => ({
    default: m.DashboardScreen,
  })),
)
const MemberDetailScreen = lazy(() =>
  import('./screens/private/members/MemberDetail').then((m) => ({
    default: m.MemberDetailScreen,
  })),
)
const GroupsScreen = lazy(() =>
  import('./screens/private/members/Groups').then((m) => ({
    default: m.GroupsScreen,
  })),
)
const InvoiceDetailScreen = lazy(() =>
  import('./screens/private/finances/InvoiceDetail').then((m) => ({
    default: m.InvoiceDetailScreen,
  })),
)
const MembersTabScreen = lazy(() =>
  import('./screens/private/members/MembersTabScreen').then((m) => ({
    default: m.MembersTabScreen,
  })),
)
const OperationsTabScreen = lazy(() =>
  import('./screens/private/operations/OperationsTabScreen').then((m) => ({
    default: m.OperationsTabScreen,
  })),
)
const FinanceTabScreen = lazy(() =>
  import('./screens/private/finances/FinanceTabScreen').then((m) => ({
    default: m.FinanceTabScreen,
  })),
)
const MailScreen = lazy(() =>
  import('./screens/private/mail/MailScreen').then((m) => ({
    default: m.MailScreen,
  })),
)
const SettingsScreen = lazy(() =>
  import('./screens/private/settings/Settings').then((m) => ({
    default: m.SettingsScreen,
  })),
)
const AuditLogScreen = lazy(() =>
  import('./screens/private/system/AuditLog').then((m) => ({
    default: m.AuditLogScreen,
  })),
)
const AccountDashboardScreen = lazy(() =>
  import('./screens/private/account/Account').then((m) => ({
    default: m.AccountDashboardScreen,
  })),
)
const AccountSettingsScreen = lazy(() =>
  import('./screens/private/account/AccountSettings').then((m) => ({
    default: m.AccountSettingsScreen,
  })),
)
const InventoryScreen = lazy(() =>
  import('./screens/private/operations/Inventory').then((m) => ({
    default: m.InventoryScreen,
  })),
)
const InventoryItemDetailScreen = lazy(() =>
  import('./screens/private/operations/InventoryItemDetail').then((m) => ({
    default: m.InventoryItemDetailScreen,
  })),
)
const SystemScreen = lazy(() =>
  import('./screens/private/system/System').then((m) => ({
    default: m.SystemScreen,
  })),
)
const TranslationsScreen = lazy(() =>
  import('./screens/private/system/Translations').then((m) => ({
    default: m.TranslationsScreen,
  })),
)
const AccessDeniedScreen = lazy(() =>
  import('./screens/private/AccessDenied').then((m) => ({
    default: m.AccessDeniedScreen,
  })),
)
const KeysScreen = lazy(() =>
  import('./screens/private/operations/Keys').then((m) => ({
    default: m.KeysScreen,
  })),
)
const CodesScreen = lazy(() =>
  import('./screens/private/operations/Codes').then((m) => ({
    default: m.CodesScreen,
  })),
)
const BindingsScreen = lazy(() =>
  import('./screens/private/operations/Bindings').then((m) => ({
    default: m.BindingsScreen,
  })),
)
const PostDetailScreen = lazy(() =>
  import('./screens/private/operations/PostDetailScreen').then((m) => ({
    default: m.PostDetailScreen,
  })),
)

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { authStatus } = useApp()
  useEffect(() => {
    if (authStatus === 'anon') {
      const currentUrl = window.location.origin + window.location.pathname
      window.location.assign(`${SSO_URL}/login?redirect=${encodeURIComponent(currentUrl)}`)
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

function RequirePermission({ permKey, children }: { permKey: string; children: React.ReactNode }) {
  const { hasPermission } = useApp()
  if (!hasPermission(permKey)) return <AccessDeniedScreen />
  return <>{children}</>
}

function SsoRedirect({ path }: { path: string }) {
  useEffect(() => {
    window.location.assign(`${SSO_URL}/${path}`)
  }, [path])
  return (
    <Center h="100vh">
      <Loader />
    </Center>
  )
}

function PrivateRoutes() {
  const location = useLocation()
  const { tenantSlug, switchTenant } = useApp()
  const { tenantSlug: urlSlug } = useParams<{ tenantSlug: string }>()

  useEffect(() => {
    if (urlSlug && urlSlug !== tenantSlug) {
      switchTenant(urlSlug)
    }
  }, [urlSlug, tenantSlug, switchTenant])

  return (
    <RequireAuth>
      <Suspense
        fallback={
          <Center h="100vh">
            <Loader />
          </Center>
        }
      >
        <Shell>
          <RouteErrorBoundary
            resetKeys={[location.pathname]}
            onReset={() => window.location.reload()}
            fallbackRender={({ resetErrorBoundary }) => (
              <Center h="100vh" p="lg">
                <Paper shadow="lg" p="xl" maw={460}>
                  <Stack gap="sm" align="center">
                    <IconAlertTriangle size={40} color="#dc2626" />
                    <Text fz={18} fw={700} c="red">
                      Something went wrong
                    </Text>
                    <Text size="sm" c="dimmed" lh={1.6} ta="center">
                      An unexpected error occurred while loading this page.
                    </Text>
                    <Button onClick={() => resetErrorBoundary()}>Retry</Button>
                  </Stack>
                </Paper>
              </Center>
            )}
          >
            <Suspense
              fallback={
                <Center h="100vh">
                  <Loader />
                </Center>
              }
            >
              <Routes>
                <Route path="dashboard" element={<DashboardScreen />} />
                <Route path="dashboard/global" element={<DashboardScreen />} />
                <Route path="members" element={<MembersTabScreen />} />
                <Route path="members/:id" element={<MemberDetailScreen />} />
                <Route path="members/applications" element={<MembersTabScreen />} />
                <Route path="members/tiers" element={<MembersTabScreen />} />
                <Route
                  path="members/functions"
                  element={
                    <RequireModule code="functions">
                      <MembersTabScreen />
                    </RequireModule>
                  }
                />
                <Route
                  path="groups"
                  element={
                    <RequireModule code="groups">
                      <GroupsScreen />
                    </RequireModule>
                  }
                />
                <Route
                  path="operations/events"
                  element={
                    <RequireModule code="events">
                      <OperationsTabScreen />
                    </RequireModule>
                  }
                />
                <Route
                  path="operations/polls"
                  element={
                    <RequireModule code="polls">
                      <OperationsTabScreen />
                    </RequireModule>
                  }
                />
                <Route
                  path="operations/posts/:id"
                  element={
                    <RequireModule code="posts">
                      <PostDetailScreen />
                    </RequireModule>
                  }
                />
                <Route
                  path="operations/posts"
                  element={
                    <RequireModule code="posts">
                      <OperationsTabScreen />
                    </RequireModule>
                  }
                />
                <Route
                  path="finance"
                  element={
                    <RequireModule code="finance">
                      <FinanceTabScreen />
                    </RequireModule>
                  }
                />
                <Route
                  path="finance/transactions"
                  element={
                    <RequireModule code="finance">
                      <FinanceTabScreen />
                    </RequireModule>
                  }
                />
                <Route
                  path="finance/invoices"
                  element={
                    <RequireModule code="finance">
                      <FinanceTabScreen />
                    </RequireModule>
                  }
                />
                <Route
                  path="finance/invoices/:id"
                  element={
                    <RequireModule code="finance">
                      <InvoiceDetailScreen />
                    </RequireModule>
                  }
                />
                <Route
                  path="finance/categories"
                  element={
                    <RequireModule code="finance">
                      <FinanceTabScreen />
                    </RequireModule>
                  }
                />
                <Route
                  path="finance/external-parties"
                  element={
                    <RequireModule code="finance">
                      <FinanceTabScreen />
                    </RequireModule>
                  }
                />
                <Route
                  path="mail"
                  element={
                    <RequireModule code="mail">
                      <MailScreen />
                    </RequireModule>
                  }
                />
                <Route
                  path="mail/system"
                  element={
                    <RequireModule code="mail">
                      <MailScreen />
                    </RequireModule>
                  }
                />
                <Route
                  path="mail/all"
                  element={
                    <RequireModule code="mail">
                      <MailScreen />
                    </RequireModule>
                  }
                />
                <Route
                  path="mail/wildduck"
                  element={
                    <RequireModule code="mail">
                      <MailScreen />
                    </RequireModule>
                  }
                />
                <Route
                  path="operations/codes"
                  element={
                    <RequireModule code="codes">
                      <CodesScreen />
                    </RequireModule>
                  }
                />
                <Route
                  path="operations/bindings"
                  element={
                    <RequireModule code="bindings">
                      <RequirePermission permKey="bindings.bindings.read">
                        <BindingsScreen />
                      </RequirePermission>
                    </RequireModule>
                  }
                />
                <Route
                  path="operations/bindings/list"
                  element={
                    <RequireModule code="bindings">
                      <RequirePermission permKey="bindings.bindings.read">
                        <BindingsScreen />
                      </RequirePermission>
                    </RequireModule>
                  }
                />
                <Route
                  path="inventory"
                  element={
                    <RequireModule code="inventory">
                      <InventoryScreen />
                    </RequireModule>
                  }
                />
                <Route
                  path="inventory/keys"
                  element={
                    <RequireModule code="inventory.keys">
                      <RequirePermission permKey="keys.keys.read">
                        <KeysScreen />
                      </RequirePermission>
                    </RequireModule>
                  }
                />
                <Route
                  path="inventory/:id"
                  element={
                    <RequireModule code="inventory">
                      <InventoryItemDetailScreen />
                    </RequireModule>
                  }
                />
                <Route
                  path="settings"
                  element={
                    <RequirePermission permKey="settings.settings.read">
                      <SettingsScreen />
                    </RequirePermission>
                  }
                />
                <Route
                  path="settings/modules"
                  element={
                    <RequirePermission permKey="settings.settings.read">
                      <SettingsScreen />
                    </RequirePermission>
                  }
                />
                <Route
                  path="settings/club"
                  element={
                    <RequirePermission permKey="settings.settings.read">
                      <SettingsScreen />
                    </RequirePermission>
                  }
                />
                <Route
                  path="settings/domains"
                  element={
                    <RequirePermission permKey="settings.settings.read">
                      <SettingsScreen />
                    </RequirePermission>
                  }
                />
                <Route
                  path="system"
                  element={
                    <RequirePermission permKey="roles.roles.create">
                      <SystemScreen />
                    </RequirePermission>
                  }
                />
                <Route
                  path="system/roles"
                  element={
                    <RequirePermission permKey="roles.roles.create">
                      <SystemScreen />
                    </RequirePermission>
                  }
                />
                <Route
                  path="system/health"
                  element={
                    <RequirePermission permKey="roles.roles.create">
                      <SystemScreen />
                    </RequirePermission>
                  }
                />
                <Route
                  path="system/backups"
                  element={
                    <RequireModule code="backups">
                      <RequirePermission permKey="roles.roles.create">
                        <SystemScreen />
                      </RequirePermission>
                    </RequireModule>
                  }
                />
                <Route
                  path="audit-log"
                  element={
                    <RequirePermission permKey="audit.audit.read">
                      <AuditLogScreen />
                    </RequirePermission>
                  }
                />
                <Route
                  path="translations"
                  element={
                    <RequirePermission permKey="i18n.i18n.write">
                      <TranslationsScreen />
                    </RequirePermission>
                  }
                />
                <Route path="account" element={<AccountDashboardScreen />} />
                <Route path="account/settings" element={<AccountSettingsScreen />} />
                <Route path="account/settings/membership" element={<AccountSettingsScreen />} />
                <Route path="account/settings/security" element={<AccountSettingsScreen />} />
                <Route path="account/settings/sessions" element={<AccountSettingsScreen />} />
                <Route path="account/settings/devices" element={<AccountSettingsScreen />} />
                <Route path="account/settings/language" element={<AccountSettingsScreen />} />
                <Route path="*" element={<Navigate to="dashboard" replace />} />
              </Routes>
            </Suspense>
          </RouteErrorBoundary>
        </Shell>
      </Suspense>
    </RequireAuth>
  )
}

function AppInner() {
  return (
    <Routes>
      {/* Auth routes — redirect to SSO portal */}
      <Route path="/login" element={<SsoRedirect path="login" />} />
      <Route path="/forgot-password" element={<SsoRedirect path="forgot-password" />} />
      <Route path="/reset-password" element={<SsoRedirect path="reset-password" />} />
      <Route path="/verify-email" element={<SsoRedirect path="verify-email" />} />

      {/* Public — tenant-specific */}
      <Route path="/apply" element={<ApplyScreen />} />

      {/* / and legacy /app/* → redirect to SSO (resolves tenant, redirects back with slug) */}
      <Route path="/" element={<SsoRedirect path="login" />} />
      <Route path="/app/*" element={<SsoRedirect path="login" />} />

      {/* Private — tenant-scoped */}
      <Route path="/:tenantSlug/app/*" element={<PrivateRoutes />} />

      {/* Default */}
      <Route path="/*" element={<NotFoundScreen />} />
    </Routes>
  )
}

function BackendBanner() {
  const { t } = useT()
  const { backendOnline, recheckBackend } = useApp()
  const [rechecking, setRechecking] = useState(false)

  if (backendOnline) return null

  const handleRecheck = async () => {
    setRechecking(true)
    await recheckBackend()
    setRechecking(false)
  }

  return (
    <Overlay fixed color="#000" backgroundOpacity={0.4} blur={4} zIndex={9999}>
      <Center h="100vh">
        <Paper bg="#fef3cd" c="#856404" radius="lg" shadow="xl" p="xl" maw={420} ta="center">
          <Stack align="center" gap="md">
            <IconAlertTriangle size={40} />
            <Text fz={18} fw={600}>
              {t('app.backendUnreachable')}
            </Text>
            <Text size="sm" lh={1.5}>
              {t('app.backendUnreachableMsg')}
            </Text>
            <Button
              variant="default"
              leftSection={<IconRefresh size={16} className={rechecking ? 'spin' : ''} />}
              onClick={handleRecheck}
              loading={rechecking}
              mt={4}
            >
              {rechecking ? t('app.checking') : t('app.retry')}
            </Button>
          </Stack>
        </Paper>
      </Center>
    </Overlay>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <AppProvider>
        <BackendBanner />
        <AppInner />
        <Toasts />
      </AppProvider>
    </ErrorBoundary>
  )
}
