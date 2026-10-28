import i18n from 'i18next'
import { lazy, Suspense, useEffect, useState } from 'react'
import { Navigate, Route, Routes, useLocation, useParams } from 'react-router-dom'
import { ErrorBoundary as RouteErrorBoundary } from 'react-error-boundary'
import { useT } from '@/locales/i18n'
import { AppProvider, useApp } from '@/context/AppContext'
import { URL_CLUB } from '@/clubBase'
import { InstanceProvider, useInstance } from '@/context/InstanceContext'
import { RequireModule } from '@/modules/RequireModule'
import { usePluginLoader, usePluginRoutes } from '@/plugins'
import { NotFoundScreen } from '@/screens/public/NotFound'
import { Toasts } from '@/components/ui'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ForcedPasswordChangeModal } from '@/components/ForcedPasswordChangeModal'
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
  const { loginUrl } = useInstance()
  const { pathname } = useLocation()
  useEffect(() => {
    if (authStatus === 'anon') window.location.assign(loginUrl(pathname))
  }, [authStatus, loginUrl, pathname])
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

function FullPageLoader() {
  return (
    <Center h="100vh">
      <Loader />
    </Center>
  )
}

function SsoRedirect({ path }: { path: string }) {
  const { ssoUrl } = useInstance()
  useEffect(() => {
    // Keep ?redirect= and the #token= of mail links.
    window.location.assign(`${ssoUrl}/${path}${window.location.search}${window.location.hash}`)
  }, [ssoUrl, path])
  return <FullPageLoader />
}

function ClubApplyRedirect() {
  const { club = '' } = useParams()
  return <SsoRedirect path={`clubs/${encodeURIComponent(club)}`} />
}

/** /app/*: the club's pages, or the SSO portal when the URL names no club. */
function ClubRoutes() {
  // On club pages the router runs below /<club> (clubBase.ts).
  return URL_CLUB ? <PrivateRoutes /> : <SsoRedirect path="login" />
}

/** `/`: into the club, or to the sign-in. */
function HomeRedirect() {
  if (URL_CLUB) return <Navigate to="/app/dashboard" replace />
  return <SsoRedirect path="login" />
}

function PrivateRoutes() {
  const location = useLocation()
  const { tenantSlug, switchTenant } = useApp()

  useEffect(() => {
    if (URL_CLUB && URL_CLUB !== tenantSlug) {
      // The club in the URL becomes active; a deep link keeps its page.
      switchTenant(URL_CLUB, true)
    }
  }, [tenantSlug, switchTenant])

  const pluginsReady = usePluginLoader()
  const pluginRoutes = usePluginRoutes()

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
                      {i18n.t('app.errorTitle', 'Etwas ist schiefgelaufen')}
                    </Text>
                    <Text size="sm" c="dimmed" lh={1.6} ta="center">
                      {i18n.t('app.errorText', 'Beim Laden dieser Seite ist ein unerwarteter Fehler aufgetreten.')}
                    </Text>
                    <Button onClick={() => resetErrorBoundary()}>
                      {i18n.t('app.retry', 'Nochmals versuchen')}
                    </Button>
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
              {!pluginsReady ? (
                <Center h="50vh">
                  <Loader />
                </Center>
              ) : (
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
                  {/* Tabs that plugins add to the finance screen. */}
                  <Route
                    path="finance/:tab"
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
                    element={<Navigate to="/app/mail" replace />}
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
                    path="settings/advanced"
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
                    element={<Navigate to="/app/system" replace />}
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
                  {/* The account itself lives on the SSO portal */}
                  {['security', 'sessions', 'devices', 'language'].map((tab) => (
                    <Route
                      key={tab}
                      path={`account/settings/${tab}`}
                      element={<SsoRedirect path="account" />}
                    />
                  ))}
                  {pluginRoutes.map((r) => (
                    <Route
                      key={r.path}
                      path={r.path}
                      element={
                        <RequireModule code={r.module}>
                          {r.perm ? (
                            <RequirePermission permKey={r.perm}>
                              <r.component />
                            </RequirePermission>
                          ) : (
                            <r.component />
                          )}
                        </RequireModule>
                      }
                    />
                  ))}
                  <Route path="*" element={<Navigate to="dashboard" replace />} />
                </Routes>
              )}
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
      {/* Signed-out pages live on the SSO portal; old links still get there */}
      {['login', 'forgot-password', 'reset-password', 'verify-email'].map((path) => (
        <Route key={path} path={`/${path}`} element={<SsoRedirect path={path} />} />
      ))}

      {/* Asking to join happens on the SSO portal, signed in: /<club>/apply
          opens that club's page there, /apply the club search. */}
      <Route path="/apply" element={<SsoRedirect path="clubs" />} />
      <Route path="/:club/apply" element={<ClubApplyRedirect />} />

      {/* / and /app/* → into the club; club pages run below /<club> (clubBase.ts) */}
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/app/*" element={<ClubRoutes />} />

      {/* Default */}
      <Route path="/*" element={<NotFoundScreen />} />
    </Routes>
  )
}

/** A temporary password blocks the API, so ask for the new one before the app loads. */
function PasswordChangeGate() {
  const { passwordChangeRequired } = useApp()
  return passwordChangeRequired ? <ForcedPasswordChangeModal /> : null
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
      <InstanceProvider>
        <AppProvider>
          <BackendBanner />
          <PasswordChangeGate />
          <AppInner />
          <Toasts />
        </AppProvider>
      </InstanceProvider>
    </ErrorBoundary>
  )
}
