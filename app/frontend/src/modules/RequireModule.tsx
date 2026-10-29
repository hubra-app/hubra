import { lazy, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { Center, Loader } from '@mantine/core'
import { useApp, useData } from '@/context/AppContext'

const AccessDeniedScreen = lazy(() =>
  import('@/screens/private/AccessDenied').then((m) => ({ default: m.AccessDeniedScreen })),
)

/**
 * Renders children only while the module is on for the active club.
 *
 * A module's list screens also need one of the permissions its sidebar entry
 * asks for, so a link typed by hand doesn't open an admin screen full of
 * empty lists. Detail pages (`…/123`) are left to their own data checks:
 * a member opens their own invoice from their account page.
 */
export function RequireModule({ code, children }: { code: string; children: ReactNode }) {
  const { modules, modulesLoaded, moduleList } = useData()
  const { hasPermission } = useApp()
  const { pathname } = useLocation()
  if (!modulesLoaded)
    return (
      <Center h="50vh">
        <Loader />
      </Center>
    )
  if (!modules[code]) return <Navigate to="/app/dashboard" replace />
  const isDetail = /\/\d+(\/|$)/.test(pathname)
  const perms = moduleList.find((m) => m.code === code)?.nav.flatMap((n) => n.perms) ?? []
  if (!isDetail && perms.length > 0 && !perms.some(hasPermission)) return <AccessDeniedScreen />
  return <>{children}</>
}
