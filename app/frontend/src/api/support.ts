import { apiFetch } from '@hubra/api-client'
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

export interface RoadmapItem {
  id: number
  title: string
  description: string
  status: CaseStatus
  area: Area | null
  votes: number
  voted?: boolean
  createdAt: string
  updatedAt: string
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

export function roadmap() {
  return apiFetch<RoadmapItem[]>('/global/support/roadmap')
}

export function setVote(id: number, on: boolean) {
  return apiFetch<{ id: number; votes: number; voted: boolean }>(`/global/support/roadmap/${id}/vote`, {
    method: on ? 'POST' : 'DELETE',
  })
}
