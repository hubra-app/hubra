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
import { Button, Center, Stack, Text } from '@mantine/core'
import { notifications as mantineNotifications } from '@mantine/notifications'
import { getMyPermissions, logout as apiLogout, type PermissionsResponse } from '@/api/auth'
import { getMyTenants } from '@/api/tenants'
import { apiFetch, hasTokens, setAuthFailureHandler, SSO_URL } from '@hubra/api-client'
import { tr } from '@/lang'

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

/**
 * manage is for platform staff (any global permission) and for the owners
 * and admins of a club. Everyone else belongs on the club picker.
 */
async function mayUseManage(perms: PermissionsResponse): Promise<boolean> {
  if (perms.is_superadmin || (perms.global_permissions?.length ?? 0) > 0) return true
  try {
    const { tenants } = await getMyTenants()
    return tenants.some((t) => t.admin_level)
  } catch {
    // Not knowing is no reason to bounce between here and SSO: the API
    // still refuses what they may not do.
    return true
  }
}

function redirectToSso() {
  const currentUrl = window.location.href
  window.location.assign(`${SSO_URL}/login?redirect=${encodeURIComponent(currentUrl)}`)
}

export function AdminProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [authStatus, setAuthStatus] = useState<AuthStatus>(() => (hasTokens() ? 'loading' : 'anon'))
  const [permData, setPermData] = useState<PermissionsResponse | null>(null)
  const [offline, setOffline] = useState(false)

  useEffect(() => {
    if (!hasTokens()) {
      redirectToSso()
      return
    }

    const ctrl = new AbortController()
    let cancelled = false
    getMyPermissions(ctrl.signal)
      .then(async (data) => {
        // While support is looking at a club as a member, the session is the
        // member's: show the way back instead of sending them to the picker.
        const allowed = data.impersonation?.is_impersonating || (await mayUseManage(data))
        if (cancelled) return
        if (!allowed) {
          window.location.assign(`${SSO_URL}/clubs`)
          return
        }
        setPermData(data)
        setAuthStatus('authed')
      })
      .catch((err: unknown) => {
        if (cancelled) return
        // Server down or restarting: the session is unknown, not gone, so
        // say so instead of sending a signed-in person to the sign-in page.
        const status = (err as { status?: number })?.status
        if (status === undefined || status >= 500) {
          setOffline(true)
          return
        }
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

  const impersonating = permData?.impersonation?.is_impersonating ? permData.impersonation : null
  if (impersonating) return <ImpersonatingScreen slug={impersonating.tenant_slug} />

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
  return <AdminContext.Provider value={value}>{children}</AdminContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAdmin(): AdminAppState {
  const ctx = useContext(AdminContext)
  if (!ctx) throw new Error('useAdmin must be used within AdminProvider')
  return ctx
}

const TENANT_APP_URL = import.meta.env.VITE_TENANT_APP_URL ?? 'https://app.hubra.club'

/** manage while support access is on: back to the club, or end it here. */
function ImpersonatingScreen({ slug }: { slug: string }) {
  const [stopping, setStopping] = useState(false)
  const stop = () => {
    setStopping(true)
    apiFetch('/system/impersonation/stop', { method: 'POST' }).finally(() => {
      window.location.assign('/tenants')
    })
  }
  return (
    <Center h="100vh" p="md">
      <Stack align="center" gap="md" maw={420} ta="center">
        <Text fz={18} fw={600}>
          {tr('Support-Zugang ist aktiv', 'Support access is on')}
        </Text>
        <Text size="sm" c="dimmed">
          {tr(
            `Du siehst den Verein «${slug}» gerade als Mitglied. Beende den Zugang, um manage wieder zu nutzen.`,
            `You are viewing the club "${slug}" as a member. End support access to use manage again.`,
          )}
        </Text>
        <Button loading={stopping} onClick={stop}>
          {tr('Support-Zugang beenden', 'End support access')}
        </Button>
        <Button
          variant="default"
          component="a"
          href={`${TENANT_APP_URL}/${encodeURIComponent(slug)}/app/dashboard`}
        >
          {tr('Zurück zum Verein', 'Back to the club')}
        </Button>
      </Stack>
    </Center>
  )
}
