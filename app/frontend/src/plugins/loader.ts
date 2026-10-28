import { useEffect, useState } from 'react'
import { BASE } from '@hubra/api-client'
import { useData } from '@/context/AppContext'

/** Script loads already started, by url, so a plugin loads once per page. */
const loads = new Map<string, Promise<void>>()

function loadScript(url: string): Promise<void> {
  let p = loads.get(url)
  if (!p) {
    p = import('./host').then(
      () =>
        new Promise<void>((resolve) => {
          const s = document.createElement('script')
          s.src = url
          s.async = true
          s.onload = () => resolve()
          s.onerror = () => {
            console.error(`plugin frontend failed to load: ${url}`)
            resolve()
          }
          document.head.appendChild(s)
        }),
    )
    loads.set(url, p)
  }
  return p
}

/**
 * Loads the frontend of every plugin that has a module on for this club.
 * True once they have all loaded (or failed), so deep links to a plugin's
 * screen don't fall through to the catch-all route.
 */
export function usePluginLoader(): boolean {
  const { moduleList, modulesLoaded } = useData()
  const urls = [
    ...new Set(
      moduleList
        .filter((m) => m.enabled && m.plugin?.frontend)
        .map((m) => `${BASE}/plugins/${m.plugin!.id}/frontend.js?v=${m.plugin!.frontend}`),
    ),
  ]
  const key = urls.join(' ')
  const [loaded, setLoaded] = useState('')
  // A failed modules request must not hold the app forever.
  const [timedOut, setTimedOut] = useState(false)

  useEffect(() => {
    const id = setTimeout(() => setTimedOut(true), 8000)
    return () => clearTimeout(id)
  }, [])

  useEffect(() => {
    if (!modulesLoaded) return
    let live = true
    Promise.all(key ? key.split(' ').map(loadScript) : []).then(() => {
      if (live) setLoaded(key)
    })
    return () => {
      live = false
    }
  }, [key, modulesLoaded])

  return timedOut || (modulesLoaded && loaded === key)
}
