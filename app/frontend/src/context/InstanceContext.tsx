import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { Center, Loader } from '@mantine/core'
import { getInstance, SSO_URL, type InstanceInfo } from '@hubra/api-client'
import { withBase } from '@/clubBase'

/** Where this install's SSO portal is: sign-in and the account live there. */
interface InstanceState {
  info: InstanceInfo
  ssoUrl: string
  /** Where a signed-out visitor goes to sign in, coming back to `returnTo`. */
  loginUrl: (returnTo?: string) => string
}

// Backend unreachable: use the SSO URL the bundle was built with.
const FALLBACK: InstanceInfo = { ssoUrl: null }

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
    const ssoUrl = info.ssoUrl ?? SSO_URL
    return {
      info,
      ssoUrl,
      loginUrl: (returnTo) => {
        const target = returnTo ? window.location.origin + withBase(returnTo) : null
        return target ? `${ssoUrl}/login?redirect=${encodeURIComponent(target)}` : `${ssoUrl}/login`
      },
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
