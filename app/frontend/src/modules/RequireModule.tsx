import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { Center, Loader } from '@mantine/core'
import { useData } from '@/context/AppContext'

/** Renders children only while the module is on for the active club. */
export function RequireModule({ code, children }: { code: string; children: ReactNode }) {
  const { modules, modulesLoaded } = useData()
  if (!modulesLoaded)
    return (
      <Center h="50vh">
        <Loader />
      </Center>
    )
  if (!modules[code]) return <Navigate to="/app/dashboard" replace />
  return <>{children}</>
}
