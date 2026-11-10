import i18n from 'i18next'
import { lazy, Suspense, useEffect, useState } from 'react'
import { Navigate, Route, Routes, useLocation, useParams } from 'react-router-dom'
import { ErrorBoundary as RouteErrorBoundary } from 'react-error-boundary'
import { useT } from '@/locales/i18n'
import { AppProvider, useApp } from '@/context/AppContext'
import { URL_CLUB } from '@/clubBase'
import { lastClubPath, pwaStartPath, rememberClub } from '@/pwa'
import { redirectTo } from '@hubra/api-client'
import { InstanceProvider, useInstance } from '@/context/InstanceContext'
import { RequireModule } from '@/modules/RequireModule'
import { PluginBoundary, usePluginLoader, usePluginRoutes } from '@/plugins'
import { NotFoundScreen } from '@/screens/public/NotFound'
import { openReport } from '@/screens/private/support/reportStore'
import { Toasts } from '@/components/ui'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { ForcedPasswordChangeModal } from '@/components/ForcedPasswordChangeModal'
import { MaintenanceScreen } from '@/components/MaintenanceScreen'
import { IconAlertTriangle, IconRefresh } from '@tabler/icons-react'
import { Loader, Center, Overlay, Paper, Text, Button, Stack } from '@mantine/core'
import { MoreScreen } from './components/Shell/MoreScreen'

const Shell = lazy(() => import('./components/Shell').then((m) => ({ default: m.Shell })))

// Lazy-load private screens
const DashboardScreen = lazy(() =>
  import('./screens/private/dashboard/Dashboard').then((m) => ({
    default: m.DashboardScreen,
  })),
)
const CalendarScreen = lazy(() =>
  import('./screens/private/calendar/CalendarScreen').then((m) => ({
    default: m.CalendarScreen,
  })),
)
const FederationScreen = lazy(() =>
  import('./screens/private/federation/FederationScreen').then((m) => ({
    default: m.FederationScreen,
  })),
)
const MemberDetailScreen = lazy(() =>
  import('./screens/private/members/MemberDetail').then((m) => ({
    default: m.MemberDetailScreen,
  })),
)
const GroupDetailScreen = lazy(() =>
  import('./screens/private/members/GroupDetail').then((m) => ({
    default: m.GroupDetailScreen,
  })),
)
const FunctionDetailScreen = lazy(() =>
  import('./screens/private/members/FunctionDetail').then((m) => ({
    default: m.FunctionDetailScreen,
  })),
)
const TierDetailScreen = lazy(() =>
  import('./screens/private/members/TierDetail').then((m) => ({
    default: m.TierDetailScreen,
  })),
)
const AuditEntryDetailScreen = lazy(() =>
  import('./screens/private/system/AuditEntryDetail').then((m) => ({
    default: m.AuditEntryDetailScreen,
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
const AccountSettingsScreen = lazy(() =>
  import('./screens/private/account/AccountSettings').then((m) => ({
    default: m.AccountSettingsScreen,
  })),
)
const TranslationsScreen = lazy(() =>
  import('./screens/private/system/TranslationSuggestions').then((m) => ({
    default: m.TranslationsScreen,
  })),
)
const FeedbackScreen = lazy(() =>
  import('./screens/private/support/FeedbackScreen').then((m) => ({
    default: m.FeedbackScreen,
  })),
)
const AccessDeniedScreen = lazy(() =>
  import('./screens/private/AccessDenied').then((m) => ({
    default: m.AccessDeniedScreen,
  })),
)
const BindingsScreen = lazy(() =>
  import('./screens/private/operations/Bindings').then((m) => ({
    default: m.BindingsScreen,
  })),
)
const EventsPage = lazy(() =>
  import('./screens/private/operations/EventsPage').then((m) => ({
    default: m.EventsPage,
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
    if (authStatus === 'anon') redirectTo(loginUrl(pathname), 'anon')
  }, [authStatus, loginUrl, pathname])
  if (authStatus === 'loading' || authStatus === 'anon')
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    )
  return <>{children}</>
}

/** Shows the page when the member holds `permKey`, or one of them for a list. */
// Switching modules is its own permission; the other settings are for admins.
const SETTINGS_OR_MODULES = ['settings.settings.read', 'modules.modules.write']
// Roles and the audit log are tabs of the settings screen too.
const ANY_SETTINGS_TAB = [...SETTINGS_OR_MODULES, 'roles.roles.create', 'audit.audit.read']

function RequirePermission({ permKey, children }: { permKey: string | string[]; children: React.ReactNode }) {
  const { hasPermission } = useApp()
  const keys = Array.isArray(permKey) ? permKey : [permKey]
  if (!keys.some(hasPermission)) return <AccessDeniedScreen />
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
    redirectTo(`${ssoUrl}/${path}${window.location.search}${window.location.hash}`, `sso-${path.split('/')[0]}`)
  }, [ssoUrl, path])
  return <FullPageLoader />
}

function ClubApplyRedirect() {
  const { club = '' } = useParams()
  return <SsoRedirect path={`clubs/${encodeURIComponent(club)}`} />
}

function ClubTrialRedirect() {
  const { club = '' } = useParams()
  return <SsoRedirect path={`clubs/${encodeURIComponent(club)}/trial`} />
}

/** /app/*: the club's pages, or the SSO portal when the URL names no club. */
function ClubRoutes() {
  // On club pages the router runs below /<club> (clubBase.ts).
  if (!URL_CLUB) return <SsoRedirect path="login" />
  rememberClub(URL_CLUB)
  return <PrivateRoutes />
}

/** `/`: into the club, or to the sign-in. */
function HomeRedirect() {
  if (URL_CLUB) return <Navigate to="/app/dashboard" replace />
  // The installed app starts at /?source=pwa: open the club used last.
  const start = pwaStartPath(window.location.search)
  if (start) {
    window.location.replace(start)
    return null
  }
  return <SsoRedirect path="login" />
}

/**
 * /invoices: invoice mails before 2026-11 linked here, without the club.
 * Open the personal start page (open invoices with QR bill) of the club used
 * last, or the club list on the SSO portal.
 */
function LegacyInvoicesRedirect() {
  const target = lastClubPath('/app/dashboard/me')
  useEffect(() => {
    if (target) window.location.replace(target)
  }, [target])
  return target ? <FullPageLoader /> : <SsoRedirect path="clubs" />
}

function PrivateRoutes() {
  const location = useLocation()

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
                    <IconAlertTriangle size={40} color="var(--mantine-color-red-text)" />
                    <Text fz={18} fw={700} c="red">
                      {i18n.t('app.errorTitle', 'Etwas ist schiefgelaufen')}
                    </Text>
                    <Text size="sm" c="dimmed" lh={1.6} ta="center">
                      {i18n.t('app.errorText', 'Beim Laden dieser Seite ist ein unerwarteter Fehler aufgetreten.')}
                    </Text>
                    <Button onClick={() => resetErrorBoundary()}>
                      {i18n.t('app.retry', 'Nochmals versuchen')}
                    </Button>
                    {/* The shell is still there, so the in-app dialog opens (it records the page). */}
                    <Button variant="default" onClick={() => openReport('bug')}>
                      {i18n.t('support.menu.bug', 'Problem melden')}
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
              <Routes>
                <Route path="dashboard" element={<DashboardScreen />} />
                <Route path="calendar" element={<CalendarScreen />} />
                <Route path="dashboard/global" element={<DashboardScreen />} />
                <Route path="dashboard/me" element={<DashboardScreen />} />
                <Route path="dashboard/d/:id" element={<DashboardScreen />} />
                <Route path="members" element={<MembersTabScreen />} />
                <Route path="members/:id" element={<MemberDetailScreen />} />
                <Route
                  path="members/applications"
                  element={
                    <RequirePermission permKey="applications.applications.read">
                      <MembersTabScreen />
                    </RequirePermission>
                  }
                />
                <Route
                  path="members/stats"
                  element={
                    <RequirePermission permKey="members.members.read">
                      <MembersTabScreen />
                    </RequirePermission>
                  }
                />
                <Route
                  path="members/tiers"
                  element={
                    <RequirePermission permKey="tiers.tiers.read">
                      <MembersTabScreen />
                    </RequirePermission>
                  }
                />
                <Route
                  path="members/tiers/:id"
                  element={
                    <RequirePermission permKey="tiers.tiers.read">
                      <TierDetailScreen />
                    </RequirePermission>
                  }
                />
                <Route
                  path="members/functions"
                  element={
                    <RequireModule code="functions">
                      <RequirePermission permKey="functions.functions.read">
                        <MembersTabScreen />
                      </RequirePermission>
                    </RequireModule>
                  }
                />
                <Route
                  path="members/functions/:id"
                  element={
                    <RequireModule code="functions">
                      <RequirePermission permKey="functions.functions.read">
                        <FunctionDetailScreen />
                      </RequirePermission>
                    </RequireModule>
                  }
                />
                <Route
                  path="groups"
                  element={
                    <RequireModule code="groups">
                      <MembersTabScreen />
                    </RequireModule>
                  }
                />
                <Route
                  path="groups/:id"
                  element={
                    <RequireModule code="groups">
                      <GroupDetailScreen />
                    </RequireModule>
                  }
                />
                <Route
                  path="operations/events/trials"
                  element={
                    <RequireModule code="events">
                      <EventsPage />
                    </RequireModule>
                  }
                />
                <Route
                  path="operations/events/attendance"
                  element={
                    <RequireModule code="events">
                      <EventsPage />
                    </RequireModule>
                  }
                />
                <Route
                  path="operations/events"
                  element={
                    <RequireModule code="events">
                      <EventsPage />
                    </RequireModule>
                  }
                />
                {/* Tabs plugins add to Anlässe, such as Booking's Vor Ort. */}
                <Route
                  path="operations/events/:tab"
                  element={
                    <RequireModule code="events">
                      <EventsPage />
                    </RequireModule>
                  }
                />
                <Route
                  path="federation"
                  element={
                    <RequireModule code="federation">
                      <FederationScreen />
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
                  path="settings"
                  element={
                    <RequirePermission permKey={ANY_SETTINGS_TAB}>
                      <SettingsScreen />
                    </RequirePermission>
                  }
                />
                <Route
                  path="settings/modules"
                  element={
                    <RequirePermission permKey={SETTINGS_OR_MODULES}>
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
                {['settings/membership', 'settings/bank', 'settings/api'].map((path) => (
                  <Route
                    key={path}
                    path={path}
                    element={
                      <RequirePermission permKey="settings.settings.read">
                        <SettingsScreen />
                      </RequirePermission>
                    }
                  />
                ))}
                <Route
                  path="settings/apps"
                  element={
                    <RequirePermission permKey="apps.apps.manage">
                      <SettingsScreen />
                    </RequirePermission>
                  }
                />
                <Route
                  path="settings/encryption"
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
                  path="settings/subscription"
                  element={
                    <RequirePermission permKey="billing.billing.manage">
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
                      <SettingsScreen />
                    </RequirePermission>
                  }
                />
                <Route
                  path="system/roles"
                  element={
                    <RequirePermission permKey="roles.roles.create">
                      <SettingsScreen />
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
                      <SettingsScreen />
                    </RequirePermission>
                  }
                />
                <Route
                  path="audit-log/:id"
                  element={
                    <RequirePermission permKey="audit.audit.read">
                      <AuditEntryDetailScreen />
                    </RequirePermission>
                  }
                />
                <Route path="more" element={<MoreScreen />} />
                <Route
                  path="translations"
                  element={
                    <RequirePermission permKey="i18n.i18n.write">
                      <TranslationsScreen />
                    </RequirePermission>
                  }
                />
                <Route path="feedback" element={<FeedbackScreen />} />
                <Route path="feedback/roadmap" element={<FeedbackScreen />} />
                {/* The personal overview is the dashboard's first tab. */}
                <Route path="account" element={<Navigate to="/app/dashboard" replace />} />
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
                        <PluginBoundary key={r.path} plugin={r.plugin} notice>
                          {r.perm ? (
                            <RequirePermission permKey={r.perm}>
                              <r.component />
                            </RequirePermission>
                          ) : (
                            <r.component />
                          )}
                        </PluginBoundary>
                      </RequireModule>
                    }
                  />
                ))}
                {/* Until plugin frontends have loaded, an unknown path may
                    still be a plugin's screen: wait instead of redirecting. */}
                <Route
                  path="*"
                  element={
                    pluginsReady ? (
                      <Navigate to="/app/dashboard" replace />
                    ) : (
                      <Center h="50vh">
                        <Loader />
                      </Center>
                    )
                  }
                />
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
      {/* Signed-out pages live on the SSO portal; old links still get there */}
      {['login', 'forgot-password', 'reset-password', 'verify-email'].map((path) => (
        <Route key={path} path={`/${path}`} element={<SsoRedirect path={path} />} />
      ))}

      {/* Asking to join happens on the SSO portal, signed in: /<club>/apply
          opens that club's page there, /apply the club search. */}
      <Route path="/apply" element={<SsoRedirect path="clubs" />} />
      <Route path="/:club/apply" element={<ClubApplyRedirect />} />
      {/* The club's trial page (people who aren't members book a training) */}
      <Route path="/:club/trial" element={<ClubTrialRedirect />} />

      {/* Old invoice mail links */}
      <Route path="/invoices" element={<LegacyInvoicesRedirect />} />

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
        <Paper bg="var(--hb-surface)" shadow="xl" p="xl" maw={420} ta="center">
          <Stack align="center" gap="md">
            <IconAlertTriangle size={40} color="var(--mantine-color-orange-text)" />
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
          <MaintenanceScreen />
          <PasswordChangeGate />
          <AppInner />
          <Toasts />
        </AppProvider>
      </InstanceProvider>
    </ErrorBoundary>
  )
}
