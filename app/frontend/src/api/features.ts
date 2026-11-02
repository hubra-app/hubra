import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@hubra/api-client'
import { qk } from '@/data/keys'

/** The early-access flags for this club (manage › Einstellungen › Früher Zugang). */
export async function getFeatures(): Promise<Record<string, boolean>> {
  const res = await apiFetch<{ features: Record<string, boolean> }>('/features')
  return res.features
}

/**
 * Whether a gated feature is on for this club. Off while loading or when
 * the flag is unknown, so a gated screen never flashes on.
 *
 *   const newCalendar = useFeature('new_calendar')
 */
export function useFeature(key: string): boolean {
  const { data } = useQuery({
    queryKey: qk.features,
    queryFn: getFeatures,
    staleTime: 5 * 60_000,
  })
  return data?.[key] === true
}
