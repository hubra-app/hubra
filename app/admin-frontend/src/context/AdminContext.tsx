import {
  createContext,
  useContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { notifications as mantineNotifications } from '@mantine/notifications'
import { getMyPermissions, logout as apiLogout, type PermissionsResponse } from '@/api/auth'
import { hasTokens, setAuthFailureHandler, SSO_URL } from '@vollbuild/api-client'

export type AuthStatus = 'loading' | 'authed' | 'anon'

interface AdminAppState {
  authStatus: AuthStatus
  isSuperadmin: boolean
  permissions: string[]
  globalPermissions: string[]
  globalRoles: string[]
  hasGlobalPermission: (key: string) => boolean
  impersonation: PermissionsResponse['impersonation']
  notify: (kind: 'success' | 'error' | 'info', title: string, msg?: string) => void
  logout: () => void
}

const AdminContext = createContext<AdminAppState | null>(null)

function redirectToSso() {
  const currentUrl = window.location.href
  window.location.assign(`${SSO_URL}/login?redirect=${encodeURIComponent(currentUrl)}`)
}

export function AdminProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [authStatus, setAuthStatus] = useState<AuthStatus>(() => (hasTokens() ? 'loading' : 'anon'))
  const [permData, setPermData] = useState<PermissionsResponse | null>(null)

  useEffect(() => {
    if (!hasTokens()) {
      redirectToSso()
      return
    }

    const ctrl = new AbortController()
    let cancelled = false
    getMyPermissions(ctrl.signal)
      .then((data) => {
        if (cancelled) return
        setPermData(data)
        setAuthStatus('authed')
      })
      .catch(() => {
        if (cancelled) return
        setAuthStatus('anon')
        redirectToSso()
      })

    return () => {
      cancelled = true
      ctrl.abort()
    }
  }, [])

  useEffect(() => {
    setAuthFailureHandler(() => {
      setAuthStatus('anon')
      setPermData(null)
      queryClient.clear()
      redirectToSso()
    })
    return () => setAuthFailureHandler(null)
  }, [queryClient])

  const notify = useCallback((kind: 'success' | 'error' | 'info', title: string, msg?: string) => {
    mantineNotifications.show({
      title,
      message: msg,
      color: kind === 'error' ? 'red' : kind === 'success' ? 'green' : 'blue',
    })
  }, [])

  const logout = useCallback(() => {
    apiLogout().finally(() => {
      queryClient.clear()
      redirectToSso()
    })
  }, [queryClient])

  const globalPermissions = useMemo(() => permData?.global_permissions ?? [], [permData])
  const globalRoles = useMemo(() => permData?.global_roles ?? [], [permData])

  const hasGlobalPermission = useCallback(
    (key: string) => {
      if (permData?.is_superadmin) return true
      return globalPermissions.includes(key) || globalPermissions.includes('*')
    },
    [permData, globalPermissions],
  )

  const value = useMemo<AdminAppState>(
    () => ({
      authStatus,
      isSuperadmin: permData?.is_superadmin ?? false,
      permissions: permData?.permissions ?? [],
      globalPermissions,
      globalRoles,
      hasGlobalPermission,
      impersonation: permData?.impersonation ?? null,
      notify,
      logout,
    }),
    [authStatus, permData, globalPermissions, globalRoles, hasGlobalPermission, notify, logout],
  )

  return <AdminContext.Provider value={value}>{children}</AdminContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAdmin(): AdminAppState {
  const ctx = useContext(AdminContext)
  if (!ctx) throw new Error('useAdmin must be used within AdminProvider')
  return ctx
}
