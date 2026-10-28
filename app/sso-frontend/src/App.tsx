import { Navigate, Route, Routes } from 'react-router-dom'
import { ErrorBoundary as RouteErrorBoundary } from 'react-error-boundary'
import { Center, Loader, Paper, Stack, Text, Button } from '@mantine/core'
import { IconAlertTriangle } from '@tabler/icons-react'
import { SsoProvider, useSso } from '@/context/SsoContext'
import { LoginScreen } from '@/screens/Login'
import { SignupScreen } from '@/screens/Signup'
import { ForgotPassword } from '@/screens/ForgotPassword'
import { ResetPassword } from '@/screens/ResetPassword'
import { VerifyEmail } from '@/screens/VerifyEmail'
import { AccessDenied } from '@/screens/AccessDenied'

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
        <Route path="/access-denied" element={<AccessDenied />} />
        <Route path="/" element={<Navigate to="/login" replace />} />
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
