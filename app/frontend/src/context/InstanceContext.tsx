import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { Center, Loader } from '@mantine/core'
import { getInstance, SSO_URL, type InstanceInfo } from '@hubra/api-client'

/**
 * How this install is set up. A single-club install (backend SINGLE_CLUB)
 * has no SSO portal: sign-in, password reset and email verification happen
 * on this app's own pages.
 */
interface InstanceState {
  info: InstanceInfo
  standalone: boolean
  /** SSO portal of a multi-club install. */
  ssoUrl: string
  /** Where a signed-out visitor goes to sign in, coming back to `returnTo`. */
  loginUrl: (returnTo?: string) => string
  /** Landing page after sign-in on a single-club install. */
  homePath: string | null
}

// Backend unreachable: keep the multi-club behaviour the app had before.
const FALLBACK: InstanceInfo = { mode: 'multi', club: null, ssoUrl: null, signup: true }

const InstanceContext = createContext<InstanceState | null>(null)

export function InstanceProvider({ children }: { children: ReactNode }) {
  const [info, setInfo] = useState<InstanceInfo | null>(null)

  useEffect(() => {
    const ctrl = new AbortController()
    getInstance(ctrl.signal)
      .then(setInfo)
      .catch(() => {
        if (!ctrl.signal.aborted) setInfo(FALLBACK)
      })
    return () => ctrl.abort()
  }, [])

  const value = useMemo<InstanceState | null>(() => {
    if (!info) return null
    const standalone = info.mode === 'single'
    const ssoUrl = info.ssoUrl ?? SSO_URL
    return {
      info,
      standalone,
      ssoUrl,
      loginUrl: (returnTo) => {
        if (standalone) {
          return returnTo ? `/login?redirect=${encodeURIComponent(returnTo)}` : '/login'
        }
        const target = returnTo ? window.location.origin + returnTo : null
        return target ? `${ssoUrl}/login?redirect=${encodeURIComponent(target)}` : `${ssoUrl}/login`
      },
      // One club, so its pages live at /app/… without the club in the path.
      homePath: standalone && info.club ? '/app/dashboard' : null,
    }
  }, [info])

  if (!value)
    return (
      <Center h="100vh">
        <Loader />
      </Center>
    )
  return <InstanceContext.Provider value={value}>{children}</InstanceContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useInstance(): InstanceState {
  const ctx = useContext(InstanceContext)
  if (!ctx) throw new Error('useInstance must be used within InstanceProvider')
  return ctx
}

/** Only same-site paths are followed after sign-in, never another origin. */
// eslint-disable-next-line react-refresh/only-export-components
export function safeReturnPath(raw: string | null): string | null {
  if (!raw || !raw.startsWith('/') || raw.startsWith('//') || raw.startsWith('/\\')) return null
  return raw
}
