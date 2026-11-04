import { apiFetch } from '@hubra/api-client'
import type { RoadmapItem, RoadmapStatus } from '@hubra/ui'

export type { RoadmapItem } from '@hubra/ui'

export interface RoadmapResponse {
  statuses: RoadmapStatus[]
  items: RoadmapItem[]
}

/** Anyone: the one roadmap (planned items and ideas), with vote counts. */
export function publicRoadmap() {
  return apiFetch<RoadmapResponse>('/global/roadmap')
}

/** Signed in: the same list with the person's own votes. */
export function myRoadmap() {
  return apiFetch<RoadmapResponse>('/global/support/roadmap')
}

/** An idea votes by its case id, a planned item by its id. */
export function setVote(item: RoadmapItem, on: boolean) {
  const path =
    item.source === 'idea' && item.caseId != null
      ? `/global/support/roadmap/${item.caseId}/vote`
      : `/global/support/roadmap/items/${encodeURIComponent(item.id)}/vote`
  return apiFetch<{ id: number | string; votes: number; voted: boolean }>(path, {
    method: on ? 'POST' : 'DELETE',
  })
}
