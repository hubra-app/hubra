import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useMemo,
  type ReactNode,
  type Dispatch,
  type SetStateAction,
} from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { notifications as mantineNotifications } from '@mantine/notifications'
import type { Phase, ToastKind, Member, Invoice } from '@/types'
import {
  clearTokens,
  hasTokens,
  setAuthFailureHandler,
  resetAuthFailure,
  setTenantSlug,
  apiFetch,
} from '@hubra/api-client'
import {
  getAccount,
  logout as apiLogout,
  getMyPermissions,
  switchTenant as apiSwitchTenant,
} from '@/api/auth'
import { clearLookups } from '@/api/lookups'
import { ping } from '@/api/system'
import { getModules, type ModuleInfo } from '@/api/modules'
import { loadAllTranslationsFromApi } from '@/locales/i18n'
import { useInstance } from '@/context/InstanceContext'

export type AuthStatus = 'loading' | 'authed' | 'anon'

// Club pages need a session; the redirects to the SSO portal do not.
const PRIVATE_PATH = /^(\/[^/]+)?\/app(\/|$)/

/* ── Split context types ─────────────────────── */

interface ToastState {
  notify: (kind: ToastKind, title: string, msg?: string) => void
}

interface AuthState {
  phase: Phase
  authStatus: AuthStatus
  tenantSlug: string | null
  currentUser: Member | null
  setCurrentUser: (m: Member | null) => void
  isAdmin: boolean
  /** Platform superadmin: sees tools that span every club. */
  isSuperadmin: boolean
  permissions: string[]
  hasPermission: (key: string) => boolean
  setPhase: (p: Phase) => void
  clearMustChangePassword: () => void
  /** Signed in, but the API answers nothing until the password is changed. */
  passwordChangeRequired: boolean
  impersonation: {
    is_impersonating: boolean
    impersonator_id: number
    tenant_slug: string
    reason: string | null
    expires_at: string | null
    restricted_actions: string[]
  } | null
  stopImpersonation: () => void
}

interface NavState {
  sidebarCollapsed: boolean
  setSidebarCollapsed: (v: boolean) => void
  mobileDrawerOpen: boolean
  setMobileDrawerOpen: (v: boolean) => void
  notifPanelOpen: boolean
  setNotifPanelOpen: (v: boolean) => void
  userMenuOpen: boolean
  setUserMenuOpen: (v: boolean) => void
  selectedMember: Member | null
  selectedInvoice: Invoice | null
  setSelectedInvoice: Dispatch<SetStateAction<Invoice | null>>
  go: (path: string, member?: Member) => void
  goInvoice: (inv: Invoice) => void
}

interface DataState {
  backendOnline: boolean
  recheckBackend: () => void
  /** Module code → effectively on for the active club. */
  modules: Record<string, boolean>
  moduleList: ModuleInfo[]
  modulesLoaded: boolean
  /** Make `slug` the active club; opens its dashboard unless `keepPath`. */
  switchTenant: (slug: string, keepPath?: boolean) => void
}

type AppState = ToastState & AuthState & NavState & DataState

/* ── Context objects ─────────────────────────── */

const ToastContext = createContext<ToastState | null>(null)
const AuthContext = createContext<AuthState | null>(null)
const NavContext = createContext<NavState | null>(null)
const DataContext = createContext<DataState | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()

  const [phase, setPhaseState] = useState<Phase>('login')
  const [authStatus, setAuthStatus] = useState<AuthStatus>('loading')
  const [tenantSlug, setTenantSlugState] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const [currentUser, setCurrentUser] = useState<Member | null>(null)
  const [selectedMember, setSelectedMember] = useState<Member | null>(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false)
  const [notifPanelOpen, setNotifPanelOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)

  const [backendOnline, setBackendOnline] = useState(true)
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null)
  const [permissions, setPermissions] = useState<string[]>([])
  const [impersonation, setImpersonation] = useState<AuthState['impersonation']>(null)
  const [isSuperadmin, setIsSuperadmin] = useState(false)
  const [passwordChangeRequired, setPasswordChangeRequired] = useState(false)

  const { loginUrl, ssoUrl } = useInstance()

  const redirectToLogin = useCallback(() => {
    if (!PRIVATE_PATH.test(window.location.pathname)) return
    window.location.assign(loginUrl(window.location.pathname))
  }, [loginUrl])

  useEffect(() => {
    const ctrl = new AbortController()
    let cancelled = false

    const checkSession = async () => {
      if (!hasTokens()) {
        if (!cancelled) {
          setAuthStatus('anon')
          redirectToLogin()
        }
        return
      }

      try {
        const member = await getAccount(ctrl.signal)
        if (cancelled) return
        setCurrentUser(member)
        try {
          const permData = await getMyPermissions(ctrl.signal)
          if (cancelled) return
          setPermissions(permData.permissions)
          setImpersonation(permData.impersonation ?? null)
          setIsSuperadmin(permData.is_superadmin === true)
        } catch {
          if (!cancelled) setPermissions([])
        }
        if (!cancelled) {
          setAuthStatus('authed')
          setPhaseState('app')
          resetAuthFailure()
        }
      } catch (err: unknown) {
        if (cancelled) return
        if ((err as { noTenant?: boolean })?.noTenant) {
          clearLookups()
          if (!cancelled) {
            setAuthStatus('anon')
            resetAuthFailure()
          }
          window.location.assign(loginUrl())
          return
        }
        const { status, code } = err as { status?: number; code?: string }
        if (status === 403 && code === 'MUST_CHANGE_PASSWORD') {
          // Stays 'loading': only the password change form is shown.
          setPasswordChangeRequired(true)
          return
        }
        if (status === 401) {
          clearTokens()
          clearLookups()
          setAuthStatus('anon')
          redirectToLogin()
        } else {
          setBackendOnline(false)
          setAuthStatus('anon')
        }
      }
    }

    checkSession()
    return () => {
      cancelled = true
      ctrl.abort()
    }
    // Runs once on mount — navigate/queryClient are stable
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    setAuthFailureHandler(() => {
      setAuthStatus('anon')
      setPhaseState('login')
      clearTokens()
      clearLookups()
      setCurrentUser(null)
      setPermissions([])
      queryClient.clear()
      redirectToLogin()
    })
    return () => setAuthFailureHandler(null)
  }, [queryClient, redirectToLogin])

  const queryEnabled = authStatus === 'authed'

  useEffect(() => {
    if (authStatus === 'authed') {
      loadAllTranslationsFromApi()
    }
  }, [authStatus])

  const { data: modulesData } = useQuery({
    queryKey: ['modules'],
    queryFn: getModules,
    enabled: queryEnabled,
  })
  const moduleList = useMemo(() => modulesData ?? [], [modulesData])
  const modulesMap = useMemo(() => {
    const map: Record<string, boolean> = {}
    for (const m of moduleList) map[m.code] = m.enabled
    return map
  }, [moduleList])
  const modulesLoaded = modulesData !== undefined

  const setActiveTenant = useCallback((slug: string | null) => {
    setTenantSlug(slug)
    setTenantSlugState(slug)
  }, [])

  const switchTenant = useCallback(
    (slug: string, keepPath = false) => {
      apiSwitchTenant(slug)
        .then(() => {
          setActiveTenant(slug)
          // The router runs below /<club>: another club is a new page.
          if (!keepPath) window.location.assign(`/${encodeURIComponent(slug)}/app/dashboard`)
        })
        .catch((err: { code?: string }) => {
          // The email step after sign-in is still open: do it on SSO first.
          if (err?.code === 'EMAIL_NOT_VERIFIED') {
            const back = encodeURIComponent(window.location.href)
            window.location.assign(`${ssoUrl}/verify?redirect=${back}`)
          }
        })
    },
    [setActiveTenant, ssoUrl],
  )

  useEffect(() => {
    const ctrl = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined
    let failures = 0

    // A hidden tab is throttled or frozen by the browser, and its requests can
    // fail without the server being down. So polling pauses while the tab is
    // hidden, a fresh check runs when it comes back, and the banner only shows
    // after two failed checks in a row.
    const schedule = (delay: number) => {
      clearTimeout(timer)
      timer = document.hidden ? undefined : setTimeout(check, delay)
    }

    const check = async () => {
      let healthy: boolean
      try {
        const { status } = await ping({ signal: ctrl.signal })
        healthy = status === 'ok' || status === 'degraded'
      } catch {
        healthy = false
      }
      if (ctrl.signal.aborted) return
      if (healthy) {
        failures = 0
        setBackendOnline(true)
        schedule(30_000)
      } else {
        failures += 1
        if (failures >= 2) setBackendOnline(false)
        // Retry soon after the first failure; back off once the banner is up.
        schedule(failures >= 2 ? 30_000 : 5_000)
      }
    }

    const onVisibilityChange = () => {
      if (document.hidden) {
        clearTimeout(timer)
        timer = undefined
      } else {
        failures = 0
        check()
      }
    }

    document.addEventListener('visibilitychange', onVisibilityChange)
    check()
    return () => {
      document.removeEventListener('visibilitychange', onVisibilityChange)
      clearTimeout(timer)
      ctrl.abort()
    }
  }, [])

  const setPhase = useCallback(
    (p: Phase) => {
      setPhaseState(p)
      if (p === 'login') {
        setAuthStatus('anon')
        apiLogout()
          .catch(() => {})
          .finally(() => {
            clearTokens()
            clearLookups()
            setCurrentUser(null)
            setPermissions([])
            queryClient.clear()
          })
        redirectToLogin()
      }
      if (p === 'app') {
        setAuthStatus('authed')
        navigate('/app/dashboard', { replace: true })
      }
    },
    [navigate, queryClient, redirectToLogin],
  )

  const go = useCallback(
    (path: string, member?: Member) => {
      if (member) {
        setSelectedMember(member)
        navigate(`/app/members/${member.id}`)
      } else {
        navigate(path)
      }
      setNotifPanelOpen(false)
      setMobileDrawerOpen(false)
      setUserMenuOpen(false)
    },
    [navigate],
  )

  const notify = useCallback((kind: ToastKind, title: string, msg?: string) => {
    const color =
      kind === 'success'
        ? 'green'
        : kind === 'error'
          ? 'red'
          : kind === 'warning'
            ? 'yellow'
            : 'blue'
    mantineNotifications.show({
      title,
      message: msg,
      color,
      withBorder: true,
      autoClose: 4000,
    })
  }, [])

  const goInvoice = useCallback(
    (inv: Invoice) => {
      setSelectedInvoice(inv)
      navigate(`/app/finance/invoices/${inv.id}`)
      setNotifPanelOpen(false)
      setMobileDrawerOpen(false)
      setUserMenuOpen(false)
    },
    [navigate],
  )

  const recheckBackend = useCallback(async () => {
    try {
      await ping()
      setBackendOnline(true)
    } catch {
      setBackendOnline(false)
    }
  }, [])

  // The API answers ['*'] for every admin role, the club's Owner included.
  const isAdmin = (currentUser?.roles?.includes('Admin') ?? false) || permissions.includes('*')

  const hasPermission = useCallback(
    (key: string) => {
      if (isAdmin) return true
      return permissions.includes(key)
    },
    [isAdmin, permissions],
  )

  const clearMustChangePassword = useCallback(() => {
    // Nothing was loaded yet, so start the app over now that the API answers.
    if (passwordChangeRequired) window.location.reload()
    setCurrentUser((prev) => (prev ? { ...prev, mustChangePassword: false } : prev))
  }, [passwordChangeRequired])

  const stopImpersonation = useCallback(() => {
    const adminUrl = import.meta.env.VITE_ADMIN_PORTAL_URL ?? 'https://manage.hubra.club'
    apiFetch('/system/impersonation/stop', { method: 'POST' }).finally(() => {
      window.location.href = `${adminUrl}/tenants`
    })
  }, [])

  /* ── Split context values ───────────────────── */

  const toastValue = useMemo<ToastState>(() => ({ notify }), [notify])

  const authValue = useMemo<AuthState>(
    () => ({
      phase,
      authStatus,
      tenantSlug,
      currentUser,
      setCurrentUser,
      isAdmin,
      isSuperadmin,
      permissions,
      hasPermission,
      setPhase,
      clearMustChangePassword,
      passwordChangeRequired,
      impersonation,
      stopImpersonation,
    }),
    // Stable callbacks (useCallback) intentionally excluded
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      phase,
      authStatus,
      tenantSlug,
      currentUser,
      isAdmin,
      isSuperadmin,
      permissions,
      impersonation,
      passwordChangeRequired,
    ],
  )

  const navValue = useMemo<NavState>(
    () => ({
      sidebarCollapsed,
      setSidebarCollapsed,
      mobileDrawerOpen,
      setMobileDrawerOpen,
      notifPanelOpen,
      setNotifPanelOpen,
      userMenuOpen,
      setUserMenuOpen,
      selectedMember,
      selectedInvoice,
      setSelectedInvoice,
      go,
      goInvoice,
    }),
    // Stable callbacks (useCallback) intentionally excluded
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      sidebarCollapsed,
      mobileDrawerOpen,
      notifPanelOpen,
      userMenuOpen,
      selectedMember,
      selectedInvoice,
    ],
  )

  const dataValue = useMemo<DataState>(
    () => ({
      backendOnline,
      recheckBackend,
      modules: modulesMap,
      moduleList,
      modulesLoaded,
      switchTenant,
    }),
    // Stable callbacks (useCallback) intentionally excluded
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      backendOnline,
      modulesMap,
      moduleList,
      modulesLoaded,
    ],
  )

  return (
    <ToastContext.Provider value={toastValue}>
      <AuthContext.Provider value={authValue}>
        <NavContext.Provider value={navValue}>
          <DataContext.Provider value={dataValue}>{children}</DataContext.Provider>
        </NavContext.Provider>
      </AuthContext.Provider>
    </ToastContext.Provider>
  )
}

/* ── Narrow hooks (opt-in for re-render optimization) ── */

// eslint-disable-next-line react-refresh/only-export-components
export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within AppProvider')
  return ctx
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AppProvider')
  return ctx
}

// eslint-disable-next-line react-refresh/only-export-components
export function useNav() {
  const ctx = useContext(NavContext)
  if (!ctx) throw new Error('useNav must be used within AppProvider')
  return ctx
}

// eslint-disable-next-line react-refresh/only-export-components
export function useData() {
  const ctx = useContext(DataContext)
  if (!ctx) throw new Error('useData must be used within AppProvider')
  return ctx
}

/* ── Backward-compatible merged hook ──────────── */

// eslint-disable-next-line react-refresh/only-export-components
export function useApp(): AppState {
  const toast = useContext(ToastContext)
  const auth = useContext(AuthContext)
  const nav = useContext(NavContext)
  const data = useContext(DataContext)
  if (!toast || !auth || !nav || !data) throw new Error('useApp must be used within AppProvider')
  return { ...toast, ...auth, ...nav, ...data }
}
