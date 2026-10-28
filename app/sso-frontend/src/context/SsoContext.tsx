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
import { hasTokens, setAuthFailureHandler } from '@hubra/api-client'
import { useNavigate } from 'react-router-dom'
import { getMyPermissions, type PermissionsResponse } from '@/api/auth'
import { signedInTarget, validateRedirect, type AppUrls } from '@/redirect'

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
  /** Leave for wherever a signed-in user belongs (see signedInTarget). */
  continueSignedIn: (perms: PermissionsResponse, tenantSlug?: string | null) => void
  notify: (kind: 'success' | 'error' | 'info', title: string, msg?: string) => void
}

const SsoContext = createContext<SsoState | null>(null)

const URLS: AppUrls = {
  cos: import.meta.env.VITE_COS_URL ?? 'https://app.hubra.club',
  manage: import.meta.env.VITE_MANAGE_URL ?? 'https://manage.hubra.club',
}

/** Pages a signed-in visitor stays on instead of being sent on. */
const SIGNED_IN_PAGES = ['/clubs']

// eslint-disable-next-line react-refresh/only-export-components
export function isManager(perms: PermissionsResponse | null): boolean {
  return !!perms && (perms.is_superadmin || (perms.global_permissions?.length ?? 0) > 0)
}

export function SsoProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const [authStatus, setAuthStatus] = useState<AuthStatus>('loading')
  const [permissions, setPermissions] = useState<PermissionsResponse | null>(null)

  const { redirectTarget, errorParam } = useMemo(() => {
    const params = new URLSearchParams(window.location.search)
    return {
      redirectTarget: validateRedirect(params.get('redirect'), URLS, { dev: import.meta.env.DEV }),
      errorParam: params.get('error'),
    }
  }, [])

  const isSuperadmin = permissions?.is_superadmin ?? false

  const continueSignedIn = useCallback(
    (perms: PermissionsResponse, tenantSlug?: string | null) => {
      const target = signedInTarget(
        {
          redirect: redirectTarget,
          isManager: isManager(perms),
          tenantSlug: tenantSlug ?? perms.tenant_slug,
        },
        URLS,
      )
      if (target) {
        window.location.assign(target)
      } else {
        // No club yet: the club picker, not the manager portal.
        setPermissions(perms)
        setAuthStatus('authed')
        navigate('/clubs', { replace: true })
      }
    },
    [redirectTarget, navigate],
  )

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

        if (SIGNED_IN_PAGES.includes(window.location.pathname)) {
          setAuthStatus('authed')
          return
        }
        continueSignedIn(permData)
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
      isManager: isManager(permissions),
      permissions,
      redirectTarget,
      urls: URLS,
      continueSignedIn,
      notify,
    }),
    [authStatus, isSuperadmin, permissions, redirectTarget, continueSignedIn, notify],
  )

  return <SsoContext.Provider value={value}>{children}</SsoContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useSso(): SsoState {
  const ctx = useContext(SsoContext)
  if (!ctx) throw new Error('useSso must be used within SsoProvider')
  return ctx
}
