import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { ErrorBoundary as RouteErrorBoundary } from 'react-error-boundary'
import { Center, Loader, Paper, Stack, Text, Button } from '@mantine/core'
import { IconAlertTriangle } from '@tabler/icons-react'
import { SsoProvider, useSso } from '@/context/SsoContext'
import { LoginScreen } from '@/screens/Login'
import { SignupScreen } from '@/screens/Signup'
import { ForgotPassword } from '@/screens/ForgotPassword'
import { ResetPassword } from '@/screens/ResetPassword'
import { VerifyEmail } from '@/screens/VerifyEmail'
import { NotMe } from '@/screens/NotMe'
import { ClubsScreen } from '@/screens/Clubs'
import { JoinClubScreen } from '@/screens/JoinClub'
import { TrialScreen } from '@/screens/Trial'
import { StartClubScreen } from '@/screens/StartClub'
import { VerifyScreen } from '@/screens/Verify'
import { AccountScreen } from '@/screens/Account'
import { InviteScreen } from '@/screens/Invite'
import { ConfirmScreen } from '@/screens/Confirm'
import { OAuthAuthorizeScreen } from '@/screens/OAuthAuthorize'
import { movedToSupport } from '@/redirect'
import { tr } from '@/lang'

const SUPPORT_URL = import.meta.env.VITE_SUPPORT_URL ?? 'https://support.hubra.club'

/** /roadmap and /status moved to the support site; old links still work. */
function MovedToSupport() {
  const { pathname, search } = useLocation()
  useEffect(() => {
    window.location.replace(movedToSupport(SUPPORT_URL, pathname, search))
  }, [pathname, search])
  return (
    <Center h="100vh">
      <Loader />
    </Center>
  )
}

function RequireAnon({ children }: { children: React.ReactNode }) {
  const { authStatus } = useSso()
  if (authStatus === 'loading')
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    )
  return <>{children}</>
}

function AppRoutes() {
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
                {tr(
                  'Ein unerwarteter Fehler ist aufgetreten. Versuch es bitte nochmals.',
                  'An unexpected error occurred. Please try again.',
                )}
              </Text>
              <Button onClick={() => resetErrorBoundary()}>{tr('Nochmals versuchen', 'Retry')}</Button>
            </Stack>
          </Paper>
        </Center>
      )}
    >
      <Routes>
        <Route
          path="/login"
          element={
            <RequireAnon>
              <LoginScreen />
            </RequireAnon>
          }
        />
        <Route
          path="/signup"
          element={
            <RequireAnon>
              <SignupScreen />
            </RequireAnon>
          }
        />
        <Route
          path="/forgot-password"
          element={
            <RequireAnon>
              <ForgotPassword />
            </RequireAnon>
          }
        />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="/not-me" element={<NotMe />} />
        <Route path="/clubs" element={<ClubsScreen />} />
        <Route path="/clubs/:slug" element={<JoinClubScreen />} />
        <Route path="/clubs/:slug/trial" element={<TrialScreen />} />
        <Route path="/invite" element={<InviteScreen />} />
        <Route path="/start" element={<StartClubScreen />} />
        <Route path="/" element={<Navigate to="/clubs" replace />} />
        <Route path="/verify" element={<VerifyScreen />} />
        <Route path="/confirm" element={<ConfirmScreen />} />
        <Route path="/oauth/authorize" element={<OAuthAuthorizeScreen />} />
        <Route path="/status" element={<MovedToSupport />} />
        <Route path="/roadmap" element={<MovedToSupport />} />
        <Route path="/account" element={<AccountScreen />} />
        <Route path="/account/:tab" element={<AccountScreen />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </RouteErrorBoundary>
  )
}

export default function App() {
  return (
    <SsoProvider>
      <AppRoutes />
    </SsoProvider>
  )
}
