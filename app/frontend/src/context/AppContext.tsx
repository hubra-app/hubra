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
import type { Phase, ToastKind, Member, Poll, Invoice, ClubEvent, Post } from '@/types'
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
  getMyTenants,
  switchTenant as apiSwitchTenant,
  type MyTenant,
} from '@/api/auth'
import { clearLookups } from '@/api/lookups'
import { ping } from '@/api/system'
import { listEvents } from '@/api/events'
import { listPolls } from '@/api/polls'
import { listPosts } from '@/api/posts'
import { listInvoices } from '@/api/finance'
import { getDashboardSummary, type DashboardSummary } from '@/api/dashboard'
import { listApplications } from '@/api/applications'
import { listGroups } from '@/api/groups'
import { getModules, type ModuleInfo } from '@/api/modules'
import { loadAllTranslationsFromApi } from '@/locales/i18n'
import { useInstance } from '@/context/InstanceContext'

export type AuthStatus = 'loading' | 'authed' | 'anon'

// Club pages need a session; sign-in, password reset and /apply do not.
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
  events: ClubEvent[]
  setEvents: Dispatch<SetStateAction<ClubEvent[]>>
  polls: Poll[]
  setPolls: Dispatch<SetStateAction<Poll[]>>
  posts: Post[]
  setPosts: Dispatch<SetStateAction<Post[]>>
  invoices: Invoice[]
  setInvoices: Dispatch<SetStateAction<Invoice[]>>
  myJoinedEvents: Set<string>
  myVotes: Record<string, number>
  setMyVotes: Dispatch<SetStateAction<Record<string, number>>>
  memberCount: number
  setMemberCount: (value: number | ((prev: number) => number)) => void
  pendingApplicationCount: number
  setPendingApplicationCount: () => void
  groupCount: number
  setGroupCount: () => void
  openInvoiceCount: number
  setOpenInvoiceCount: (value: number | ((prev: number) => number)) => void
  backendOnline: boolean
  recheckBackend: () => void
  /** Module code → effectively on for the active club. */
  modules: Record<string, boolean>
  moduleList: ModuleInfo[]
  modulesLoaded: boolean
  myTenants: MyTenant[]
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

  const [myVotes, setMyVotes] = useState<Record<string, number>>({})
  const [backendOnline, setBackendOnline] = useState(true)
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null)
  const [permissions, setPermissions] = useState<string[]>([])
  const [impersonation, setImpersonation] = useState<AuthState['impersonation']>(null)
  const [passwordChangeRequired, setPasswordChangeRequired] = useState(false)

  const { standalone, loginUrl } = useInstance()

  const redirectToLogin = useCallback(() => {
    if (!PRIVATE_PATH.test(window.location.pathname)) return
    const url = loginUrl(window.location.pathname)
    if (standalone) navigate(url, { replace: true })
    else window.location.assign(url)
  }, [loginUrl, navigate, standalone])

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
          if (standalone) navigate(loginUrl(), { replace: true })
          else window.location.assign(loginUrl())
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
  // Data of a switched-off module would answer 403, so only load what is on.
  const moduleQuery = (code: string) => queryEnabled && modulesMap[code] === true

  const { data: eventsData } = useQuery({
    queryKey: ['events'],
    queryFn: () => listEvents(),
    enabled: moduleQuery('events'),
  })
  const { data: pollsData } = useQuery({
    queryKey: ['polls'],
    queryFn: listPolls,
    enabled: moduleQuery('polls'),
  })
  const { data: postsData } = useQuery({
    queryKey: ['posts'],
    queryFn: listPosts,
    enabled: moduleQuery('posts'),
  })
  const { data: invoicesData } = useQuery({
    queryKey: ['invoices'],
    queryFn: listInvoices,
    enabled: moduleQuery('finance'),
  })
  const { data: dashboardData } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: getDashboardSummary,
    enabled: queryEnabled,
  })
  const { data: applicationsData } = useQuery({
    queryKey: ['applications'],
    queryFn: listApplications,
    enabled: queryEnabled,
  })
  const { data: groupsData } = useQuery({
    queryKey: ['groups'],
    queryFn: listGroups,
    enabled: moduleQuery('groups'),
  })
  const { data: tenantsData } = useQuery({
    queryKey: ['my-tenants'],
    queryFn: () => getMyTenants(),
    enabled: queryEnabled,
  })

  const events = useMemo(() => eventsData ?? [], [eventsData])
  const polls = useMemo(() => pollsData ?? [], [pollsData])
  const posts = useMemo(() => postsData ?? [], [postsData])
  const invoices = useMemo(() => invoicesData ?? [], [invoicesData])
  const myJoinedEvents = useMemo(
    () =>
      new Set(
        events.filter((ev) => ev.attendees.includes(currentUser?.id ?? '')).map((ev) => ev.id),
      ),
    [events, currentUser],
  )
  const memberCount = dashboardData?.stats?.activeMembers ?? 0
  const openInvoiceCount = dashboardData?.stats?.openInvoices ?? 0
  const pendingApplicationCount = applicationsData?.length ?? 0
  const groupCount = groupsData?.length ?? 0

  const myTenants = useMemo(() => tenantsData?.tenants ?? [], [tenantsData])

  const setActiveTenant = useCallback((slug: string | null) => {
    setTenantSlug(slug)
    setTenantSlugState(slug)
  }, [])

  const switchTenant = useCallback(
    (slug: string, keepPath = false) => {
      apiSwitchTenant(slug).then(() => {
        setActiveTenant(slug)
        if (!keepPath) navigate(`/${slug}/app/dashboard`)
      })
    },
    [navigate, setActiveTenant],
  )

  const setEvents = useCallback(
    (updater: ClubEvent[] | ((prev: ClubEvent[]) => ClubEvent[])) => {
      queryClient.setQueryData<ClubEvent[]>(['events'], (prev) =>
        typeof updater === 'function' ? updater(prev ?? []) : updater,
      )
    },
    [queryClient],
  )
  const setPolls = useCallback(
    (updater: Poll[] | ((prev: Poll[]) => Poll[])) => {
      queryClient.setQueryData<Poll[]>(['polls'], (prev) =>
        typeof updater === 'function' ? updater(prev ?? []) : updater,
      )
    },
    [queryClient],
  )
  const setPosts = useCallback(
    (updater: Post[] | ((prev: Post[]) => Post[])) => {
      queryClient.setQueryData<Post[]>(['posts'], (prev) =>
        typeof updater === 'function' ? updater(prev ?? []) : updater,
      )
    },
    [queryClient],
  )
  const setInvoices = useCallback(
    (updater: Invoice[] | ((prev: Invoice[]) => Invoice[])) => {
      queryClient.setQueryData<Invoice[]>(['invoices'], (prev) =>
        typeof updater === 'function' ? updater(prev ?? []) : updater,
      )
    },
    [queryClient],
  )
  const setMemberCount = useCallback(
    (updater: number | ((prev: number) => number)) => {
      queryClient.setQueryData<DashboardSummary | undefined>(['dashboard-summary'], (prev) => {
        if (!prev?.stats) return prev
        const newCount = typeof updater === 'function' ? updater(prev.stats.activeMembers) : updater
        return { ...prev, stats: { ...prev.stats, activeMembers: newCount } }
      })
    },
    [queryClient],
  )
  const setOpenInvoiceCount = useCallback(
    (updater: number | ((prev: number) => number)) => {
      queryClient.setQueryData<DashboardSummary | undefined>(['dashboard-summary'], (prev) => {
        if (!prev?.stats) return prev
        const newCount = typeof updater === 'function' ? updater(prev.stats.openInvoices) : updater
        return { ...prev, stats: { ...prev.stats, openInvoices: newCount } }
      })
    },
    [queryClient],
  )
  const setPendingApplicationCount = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['applications'] })
  }, [queryClient])
  const setGroupCount = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['groups'] })
  }, [queryClient])

  useEffect(() => {
    const ctrl = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    let lastStatus: string | null = null

    const check = async () => {
      try {
        const { status } = await ping({ signal: ctrl.signal })
        if (ctrl.signal.aborted) return
        setBackendOnline(status === 'ok' || status === 'degraded')
        lastStatus = status
      } catch {
        if (!ctrl.signal.aborted) setBackendOnline(false)
        lastStatus = 'error'
      }
      // Back off to 60s when the server is not healthy; 30s otherwise.
      const delay = lastStatus === 'ok' ? 30_000 : 60_000
      timer = setTimeout(check, delay)
    }
    check()
    return () => {
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
    const adminUrl = import.meta.env.VITE_ADMIN_PORTAL_URL ?? 'https://manage.vollbuild.ch'
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
      events,
      setEvents,
      polls,
      setPolls,
      posts,
      setPosts,
      invoices,
      setInvoices,
      myJoinedEvents,
      myVotes,
      setMyVotes,
      memberCount,
      setMemberCount,
      pendingApplicationCount,
      setPendingApplicationCount,
      groupCount,
      setGroupCount,
      openInvoiceCount,
      setOpenInvoiceCount,
      backendOnline,
      recheckBackend,
      modules: modulesMap,
      moduleList,
      modulesLoaded,
      myTenants,
      switchTenant,
    }),
    // Stable callbacks (useCallback) intentionally excluded
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      events,
      polls,
      posts,
      invoices,
      myJoinedEvents,
      myVotes,
      memberCount,
      pendingApplicationCount,
      groupCount,
      openInvoiceCount,
      backendOnline,
      modulesMap,
      moduleList,
      modulesLoaded,
      myTenants,
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
