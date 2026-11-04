import { apiFetch } from '@hubra/api-client'

export type RoadmapStatus = 'open' | 'planned' | 'in_progress' | 'done'

export interface RoadmapItem {
  id: number
  title: string
  description: string
  status: RoadmapStatus
  area: string | null
  votes: number
  /** Only when signed in. */
  voted?: boolean
  createdAt: string
  updatedAt: string
}

/** Anyone: the public list. */
export function publicRoadmap() {
  return apiFetch<RoadmapItem[]>('/global/roadmap')
}

/** Signed in: the same list with the person's own votes. */
export function myRoadmap() {
  return apiFetch<RoadmapItem[]>('/global/support/roadmap')
}

export function setVote(id: number, on: boolean) {
  return apiFetch<{ id: number; votes: number; voted: boolean }>(`/global/support/roadmap/${id}/vote`, {
    method: on ? 'POST' : 'DELETE',
  })
}
