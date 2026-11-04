import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import type { RoadmapItem, RoadmapVoting } from '@hubra/ui'
import { roadmap, setVote } from '@/api/support'
import { useToast } from '@/context/AppContext'
import { useT } from '@/locales/i18n'
import { qk } from '@/data/keys'

/**
 * The one roadmap with your votes, for Neuigkeiten › Roadmap and
 * /app/feedback/roadmap (both use the shared Roadmap view from @hubra/ui).
 */
export function useRoadmap(enabled = true): {
  items: RoadmapItem[]
  isLoading: boolean
  isError: boolean
  voting: RoadmapVoting
} {
  const { t } = useT()
  const { notify } = useToast()
  const queryClient = useQueryClient()
  const [pending, setPending] = useState<string | null>(null)
  const query = useQuery({ queryKey: qk.support.roadmap, queryFn: roadmap, enabled, staleTime: 60_000 })

  const onVote = async (item: RoadmapItem) => {
    setPending(item.id)
    try {
      const res = await setVote(item, !item.voted)
      queryClient.setQueryData<Awaited<ReturnType<typeof roadmap>>>(qk.support.roadmap, (old) =>
        old
          ? { ...old, items: old.items.map((i) => (i.id === item.id ? { ...i, votes: res.votes, voted: res.voted } : i)) }
          : old,
      )
    } catch (err) {
      notify('error', t('support.roadmap.voteFailed', 'Abstimmen fehlgeschlagen'), (err as Error).message)
    } finally {
      setPending(null)
    }
  }

  return {
    items: query.data?.items ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
    voting: { onVote: (item) => void onVote(item), pending },
  }
}
