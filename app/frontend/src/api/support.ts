import { apiFetch } from '@hubra/api-client'
import type { RoadmapItem, RoadmapStatus } from '@hubra/ui'
import type { DeviceInfo } from '@/screens/private/support/deviceInfo'

export type CaseKind = 'bug' | 'feature'
export type CaseStatus = 'open' | 'planned' | 'in_progress' | 'done' | 'closed'
export type Severity = 'minor' | 'annoying' | 'blocking'

export const AREAS = [
  'members',
  'finance',
  'events',
  'posts',
  'polls',
  'groups',
  'inventory',
  'mail',
  'settings',
  'account',
  'modules',
  'other',
] as const
export type Area = (typeof AREAS)[number]

export interface CaseComment {
  id: number
  body: string
  fromStaff: boolean
  internal: boolean
  createdAt: string
  author: string | null
}

export interface SupportCase {
  id: number
  kind: CaseKind
  status: CaseStatus
  title: string
  description: string
  steps: string | null
  expected: string | null
  useCase: string | null
  area: Area | null
  severity: Severity | null
  page: string | null
  fingerprint: DeviceInfo & { appVersion?: string }
  isPublic: boolean
  roadmapItem: string | null
  mergedInto: { id: number; title: string; status: CaseStatus } | null
  votes: number
  commentCount: number
  createdAt: string
  updatedAt: string
  closedAt: string | null
  comments?: CaseComment[]
}

export interface NewCase {
  kind: CaseKind
  title: string
  description: string
  steps?: string
  expected?: string
  useCase?: string
  area?: Area | null
  severity?: Severity | null
  page?: string
  fingerprint: DeviceInfo
}

export function sendCase(body: NewCase) {
  return apiFetch<SupportCase>('/global/support/cases', { method: 'POST', body: JSON.stringify(body) })
}

export function myCases() {
  return apiFetch<SupportCase[]>('/global/support/cases')
}

export function myCase(id: number) {
  return apiFetch<SupportCase>(`/global/support/cases/${id}`)
}

export function replyToCase(id: number, body: string) {
  return apiFetch<CaseComment>(`/global/support/cases/${id}/comments`, {
    method: 'POST',
    body: JSON.stringify({ body }),
  })
}

/** The one roadmap (planned items and ideas) with your own votes. */
export function roadmap() {
  return apiFetch<{ statuses: RoadmapStatus[]; items: RoadmapItem[] }>('/global/support/roadmap')
}

/** Vote for an item: an idea by its case id, a planned item by its id. */
export function setVote(item: RoadmapItem, on: boolean) {
  const path =
    item.source === 'idea' && item.caseId != null
      ? `/global/support/roadmap/${item.caseId}/vote`
      : `/global/support/roadmap/items/${encodeURIComponent(item.id)}/vote`
  return apiFetch<{ id: number | string; votes: number; voted: boolean }>(path, {
    method: on ? 'POST' : 'DELETE',
  })
}
