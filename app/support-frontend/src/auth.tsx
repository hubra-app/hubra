import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { notifications } from '@mantine/notifications'
import { clearTokens, hasTokens, resetAuthFailure, setAuthFailureHandler } from '@hubra/api-client'
import { getProfile, type Profile } from '@/api/support'
import { signInUrl } from '@/urls'

export type AuthStatus = 'loading' | 'authed' | 'anon'

interface AuthState {
  status: AuthStatus
  profile: Profile | null
  /** The SSO sign-in page, coming back to `back` (default: this page). */
  signInUrl: (back?: string) => string
  signOut: () => void
  notify: (kind: 'success' | 'error' | 'info', title: string, msg?: string) => void
}

const AuthContext = createContext<AuthState | null>(null)


function notify(kind: 'success' | 'error' | 'info', title: string, msg?: string) {
  notifications.show({
    title,
    message: msg,
    color: kind === 'error' ? 'red' : kind === 'success' ? 'green' : 'acc',
  })
}

/**
 * The support site has no sign-in of its own: the SSO cookies are set for
 * the parent domain (JWT_COOKIE_DOMAIN=.hubra.club), so a person signed in
 * anywhere in Hubra is signed in here too. Reading pages needs no account;
 * voting, reports and privacy requests do.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>(hasTokens() ? 'loading' : 'anon')
  const [profile, setProfile] = useState<Profile | null>(null)

  useEffect(() => {
    setAuthFailureHandler(() => {
      setStatus('anon')
      setProfile(null)
    })
    return () => setAuthFailureHandler(null)
  }, [])

  useEffect(() => {
    if (!hasTokens()) return
    const ctrl = new AbortController()
    getProfile(ctrl.signal)
      .then((p) => {
        setProfile(p)
        setStatus('authed')
      })
      .catch(() => {
        if (!ctrl.signal.aborted) setStatus('anon')
      })
    return () => ctrl.abort()
  }, [])

  const signOut = useCallback(() => {
    clearTokens()
    resetAuthFailure()
    setProfile(null)
    setStatus('anon')
  }, [])

  const value = useMemo<AuthState>(
    () => ({ status, profile, signInUrl, signOut, notify }),
    [status, profile, signOut],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth outside AuthProvider')
  return ctx
}
