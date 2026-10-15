import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useMemo,
  type ReactNode,
} from 'react'
import { notifications } from '@mantine/notifications'
import { hasTokens, setAuthFailureHandler } from '@vollbuild/api-client'
import { getMyPermissions, type PermissionsResponse } from '@/api/auth'

export type AuthStatus = 'loading' | 'authed' | 'anon'

interface SsoState {
  authStatus: AuthStatus
  isSuperadmin: boolean
  permissions: PermissionsResponse | null
  redirectTarget: string
  notify: (kind: 'success' | 'error' | 'info', title: string, msg?: string) => void
}

const SsoContext = createContext<SsoState | null>(null)

const DEFAULT_COS_URL = import.meta.env.VITE_COS_URL ?? 'https://cos.vollbuild.ch'
const DEFAULT_MANAGE_URL = import.meta.env.VITE_MANAGE_URL ?? 'https://manage.vollbuild.ch'

function validateRedirect(raw: string | null): string {
  if (!raw) return DEFAULT_COS_URL
  try {
    const url = new URL(raw)
    if (url.protocol === 'http:') {
      if (url.hostname === 'localhost') return raw
    }
    if (url.protocol === 'https:') {
      if (url.hostname.endsWith('.vollbuild.ch')) return raw
    }
  } catch {
    /* fall through */
  }
  return DEFAULT_COS_URL
}

// eslint-disable-next-line react-refresh/only-export-components
export function determineDefaultRedirect(isSuperadmin: boolean): string {
  return isSuperadmin ? DEFAULT_MANAGE_URL : DEFAULT_COS_URL
}

export function SsoProvider({ children }: { children: ReactNode }) {
  const [authStatus, setAuthStatus] = useState<AuthStatus>('loading')
  const [permissions, setPermissions] = useState<PermissionsResponse | null>(null)

  const { redirectTarget, errorParam, hasExplicitRedirect } = useMemo(() => {
    const params = new URLSearchParams(window.location.search)
    const explicitRedirect = params.get('redirect')
    return {
      redirectTarget: validateRedirect(explicitRedirect),
      errorParam: params.get('error'),
      hasExplicitRedirect: explicitRedirect !== null,
    }
  }, [])

  const isSuperadmin = permissions?.is_superadmin ?? false

  useEffect(() => {
    if (errorParam === 'insufficient_permissions') {
      notifications.show({
        title: 'Access Denied',
        message: 'You do not have permission to access the admin portal.',
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

        const hasGlobalAccess =
          permData.is_superadmin || (permData.global_permissions?.length ?? 0) > 0
        if (hasGlobalAccess && !hasExplicitRedirect) {
          window.location.assign(DEFAULT_MANAGE_URL)
          return
        }

        window.location.assign(redirectTarget)
      } catch {
        if (cancelled) return
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
      permissions,
      redirectTarget,
      notify,
    }),
    [authStatus, isSuperadmin, permissions, redirectTarget, notify],
  )

  return <SsoContext.Provider value={value}>{children}</SsoContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useSso(): SsoState {
  const ctx = useContext(SsoContext)
  if (!ctx) throw new Error('useSso must be used within SsoProvider')
  return ctx
}
