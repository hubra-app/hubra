import { BASE } from '@hubra/api-client'

export type Level = 'operational' | 'degraded' | 'down'
export type Component = 'app' | 'mail' | 'notifications'
export type Overall = Level | 'maintenance'

export interface StatusPage {
  overall: Overall
  components: { id: Component; level: Level }[]
  maintenance: {
    active: boolean
    message: string
    until: string | null
    upcoming: { starts_at: string; ends_at: string; message: string } | null
  }
  incidents: { component: Component; level: Level; started_at: string; ended_at: string | null }[]
  past_maintenance: { starts_at: string; ends_at: string; message: string }[]
  history_days: number
  checked_at: string
  club: { slug: string; name: string } | null
}

export const STATUS_COLOR: Record<Overall, string> = {
  operational: 'green',
  degraded: 'orange',
  down: 'red',
  maintenance: 'acc',
}

/**
 * Public: no session, no refresh. The support site runs in its own pods, so
 * this page stays up while the rest of Hubra is upgraded or down; a failed
 * request is itself an answer ("Hubra is unreachable").
 */
export async function getStatus(club: string | null): Promise<StatusPage> {
  const qs = club ? `?club=${encodeURIComponent(club)}` : ''
  const res = await fetch(`${BASE}/global/status${qs}`, { credentials: 'omit' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return (await res.json()) as StatusPage
}
