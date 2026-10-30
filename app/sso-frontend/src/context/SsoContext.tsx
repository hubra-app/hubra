import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useMemo,
  type ReactNode,
} from 'react'
import { Button, Center, Stack, Text } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { hasTokens, setAuthFailureHandler } from '@hubra/api-client'
import { useNavigate } from 'react-router-dom'
import { getMyPermissions, getVerificationStatus, type PermissionsResponse } from '@/api/auth'
import { signedInTarget, validateRedirect, type AppUrls } from '@/redirect'
import { tr } from '@/lang'

export type AuthStatus = 'loading' | 'authed' | 'anon'

interface SsoState {
  authStatus: AuthStatus
  isSuperadmin: boolean
  /** Superadmin, or any global permission: the manager portal is theirs. */
  isManager: boolean
  permissions: PermissionsResponse | null
  /** The trusted ?redirect= target, or null when there is none. */
  redirectTarget: string | null
  urls: AppUrls
  /**
   * After sign-in: the email step if it is still open, else the ?redirect=
   * target or the club picker (see signedInTarget).
   */
  continueSignedIn: () => void
  notify: (kind: 'success' | 'error' | 'info', title: string, msg?: string) => void
}

const SsoContext = createContext<SsoState | null>(null)

const URLS: AppUrls = {
  cos: import.meta.env.VITE_COS_URL ?? 'https://app.hubra.club',
  manage: import.meta.env.VITE_MANAGE_URL ?? 'https://manage.hubra.club',
}

/** Pages a signed-in visitor stays on instead of being sent on. */
const SIGNED_IN_PAGES = ['/clubs', '/start', '/account', '/verify', '/verify-email', '/invite']

// eslint-disable-next-line react-refresh/only-export-components
export function isManager(perms: PermissionsResponse | null): boolean {
  return !!perms && (perms.is_superadmin || (perms.global_permissions?.length ?? 0) > 0)
}

/** The trusted ?redirect= of the current URL. */
function currentRedirect(): string | null {
  const raw = new URLSearchParams(window.location.search).get('redirect')
  return validateRedirect(raw, URLS, { dev: import.meta.env.DEV, self: window.location.origin })
}

export function SsoProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const [authStatus, setAuthStatus] = useState<AuthStatus>('loading')
  const [permissions, setPermissions] = useState<PermissionsResponse | null>(null)
  const [offline, setOffline] = useState(false)

  const { redirectTarget, errorParam } = useMemo(() => {
    const params = new URLSearchParams(window.location.search)
    return { redirectTarget: currentRedirect(), errorParam: params.get('error') }
  }, [])

  const isSuperadmin = permissions?.is_superadmin ?? false

  const continueSignedIn = useCallback(() => {
    // Still 'anon' right after sign-in: the next page would bounce to /login.
    setAuthStatus('loading')
    Promise.all([getMyPermissions(), getVerificationStatus()])
      .then(([perms, verification]) => {
        setPermissions(perms)
        if (verification.required) {
          // Keep ?redirect= so the step can send the person on afterwards.
          navigate(`/verify${window.location.search}`, { replace: true })
          setAuthStatus('authed')
          return
        }
        // Read now, not at start: pages such as /clubs/<slug> send anonymous
        // visitors to /login?redirect=… without reloading.
        const target = signedInTarget(currentRedirect())
        if (target) {
          window.location.assign(target)
          return
        }
        // signedIn: the picker may open the only club straight away.
        navigate('/clubs', { replace: true, state: { signedIn: true } })
        setAuthStatus('authed')
      })
      .catch(() => setAuthStatus('anon'))
  }, [navigate])

  useEffect(() => {
    if (errorParam === 'insufficient_permissions') {
      notifications.show({
        title: tr('Kein Zugriff', 'Access denied'),
        message: tr('Du hast keinen Zugriff auf die Verwaltung.', 'You do not have access to the admin portal.'),
        color: 'red',
      })
    }
  }, [errorParam])

  useEffect(() => {
    const ctrl = new AbortController()
    let cancelled = false

    const checkSession = async () => {
      if (!hasTokens()) {
        if (!cancelled) setAuthStatus('anon')
        return
      }

      try {
        const permData = await getMyPermissions(ctrl.signal)
        if (cancelled) return
        setPermissions(permData)

        const path = window.location.pathname
        if (SIGNED_IN_PAGES.some((p) => path === p || path.startsWith(`${p}/`))) {
          // Signed-in pages still wait for the email step (the link page
          // itself and the step are where it gets done).
          if (path !== '/verify' && path !== '/verify-email') {
            const verification = await getVerificationStatus(ctrl.signal)
            if (cancelled) return
            if (verification.required) {
              // An invite link keeps its token in the hash: come back to it.
              const back =
                path === '/invite'
                  ? `?redirect=${encodeURIComponent(window.location.href)}`
                  : window.location.search
              navigate(`/verify${back}`, { replace: true })
            }
          }
          setAuthStatus('authed')
          return
        }
        continueSignedIn()
      } catch (err: unknown) {
        if (cancelled) return
        // Server down or restarting: the session is unknown, not gone, so
        // say so instead of showing the sign-in form.
        const status = (err as { status?: number })?.status
        if (status === undefined || status >= 500) {
          setOffline(true)
          return
        }
        setAuthStatus('anon')
      }
    }

    checkSession()
    return () => {
      cancelled = true
      ctrl.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    setAuthFailureHandler(() => {
      setAuthStatus('anon')
      setPermissions(null)
    })
    return () => setAuthFailureHandler(null)
  }, [])

  const notify = useCallback((kind: 'success' | 'error' | 'info', title: string, msg?: string) => {
    notifications.show({
      title,
      message: msg,
      color: kind === 'error' ? 'red' : kind === 'success' ? 'green' : 'blue',
    })
  }, [])

  const value = useMemo<SsoState>(
    () => ({
      authStatus,
      isSuperadmin,
      isManager: isManager(permissions),
      permissions,
      redirectTarget,
      urls: URLS,
      continueSignedIn,
      notify,
    }),
    [authStatus, isSuperadmin, permissions, redirectTarget, continueSignedIn, notify],
  )

  if (offline)
    return (
      <Center h="100vh" p="md">
        <Stack align="center" gap="md" maw={420} ta="center">
          <Text fz={18} fw={600}>
            {tr('Der Server ist gerade nicht erreichbar', 'The server cannot be reached')}
          </Text>
          <Text size="sm" c="dimmed">
            {tr('Versuche es in einem Moment nochmals.', 'Please try again in a moment.')}
          </Text>
          <Button variant="default" onClick={() => window.location.reload()}>
            {tr('Erneut versuchen', 'Try again')}
          </Button>
        </Stack>
      </Center>
    )
  return <SsoContext.Provider value={value}>{children}</SsoContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useSso(): SsoState {
  const ctx = useContext(SsoContext)
  if (!ctx) throw new Error('useSso must be used within SsoProvider')
  return ctx
}
